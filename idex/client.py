import asyncio
from decimal import Decimal
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlencode
import uuid
from typing import Optional, Dict, List, Union, Any, Iterable, Callable

import aiohttp
from eth_account import Account
from eth_account.messages import SignableMessage, encode_defunct
import requests
from eth_account.signers.local import LocalAccount
from eth_typing import HexStr
from web3 import Web3, middleware, types as web3_types
from web3.gas_strategies.rpc import rpc_gas_price_strategy

from .enums import (
    CandleInterval,
    OrderbookLevel,
    SignType,
    OrderType,
    OrderSide,
    OrderTimeInForce,
    OrderSelfTradePrevention,
    TransactionOptions,
)
from .exceptions import (
    IdexAPIException,
    IdexRequestException,
    IdexCurrencyNotFoundException,
)
from .signing import path_signature_parameters, SigParamType
from .utils import (
    get_nonce,
    format_quantity,
    convert_to_token_quantity,
)


class BaseClient:

    API_URL = "https://api-matic.idex.io"
    SANDBOX_URL = "https://api-sandbox-matic.idex.io"

    RPC_URL = "https://polygon-rpc.com"
    SANDBOX_RPC_URL = "https://rpc-mumbai.matic.today"

    API_VERSION = "v1"

    CONTRACTS = {
        "exchange": "0x3253A7e75539EdaEb1Db608ce6Ef9AA1ac9126B6",
        "custody": "0x3bcC4EcA0a40358558ca8D1bcd2d1dBdE63eB468",
    }

    SANDBOX_CONTRACTS = {"exchange": "0x1C74657A9C53D709d93eBD7831F7adB14714CB40"}

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        requests_params: Optional[Dict] = None,
        sandbox: bool = False,
    ):
        """IDEX API Client constructor

        https://github.com/AuroraDAO/idex-api-docs

        :param api_key: optional - Wallet address
        :type api_key: address string
        :param requests_params: optional - Dictionary of requests params to use for all calls
        :type requests_params: dict.

        """

        self.api_url = self.SANDBOX_URL if sandbox else self.API_URL
        self.rpc_url = self.SANDBOX_RPC_URL if sandbox else self.RPC_URL
        self.contracts = self.SANDBOX_CONTRACTS if sandbox else self.CONTRACTS
        self.sandbox: bool = sandbox
        self._start_nonce = None
        self._client_started = int(time.time() * 1000)
        self._requests_params = requests_params
        self._last_response = None
        self._api_key: Optional[str] = api_key
        self._api_secret: Optional[str] = api_secret
        self._wallet_private_key: Optional[str] = private_key
        self._wallet: Optional[LocalAccount] = None
        self._wallet_address: Optional[str] = None
        self._asset_addresses: Dict[str, Dict] = {}
        self._faucet_abi: Optional[Dict] = None
        self._exchange_abi: Optional[Dict] = None

        self.session = self._init_session()
        self.init_wallet(private_key)

    def _get_headers(self):
        headers = {
            "Accept": "application/json",
            "User-Agent": "python-idex",
        }
        if self._api_key:
            headers["IDEX-API-Key"] = self._api_key
        return headers

    @staticmethod
    def _get_nonce() -> uuid.UUID:
        """Get a unique nonce for request"""
        return get_nonce()

    @property
    def wallet(self) -> LocalAccount:
        assert self._wallet
        return self._wallet

    @property
    def wallet_address(self) -> str:
        return self._wallet.address if self._wallet else ""

    def _sign_params(self, method: str, params: Optional[Dict] = None) -> str:
        data: Dict = params or {}
        if method == "get":
            data_str = urlencode(data)
        else:
            data_str = json.dumps(data, separators=(",", ":"))

        assert self._api_secret, "Must initialise client with api_secret to use private endpoints"
        return hmac.new(
            self._api_secret.encode("utf-8"),
            data_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def init_wallet(self, private_key: Optional[str] = None):
        if private_key:
            self._wallet_private_key = private_key
        if self._wallet_private_key:
            self._wallet = Account.from_key(self._wallet_private_key)

    def _wallet_sign(self, path: str, method: str, data: Dict) -> Dict:
        signature_parameters = path_signature_parameters(
            path, method, self.wallet_address, self.sandbox, data
        )
        params = {
            "parameters": data,
            "signature": self._create_wallet_signature(signature_parameters),
        }
        params["parameters"]["nonce"] = str(params["parameters"]["nonce"])
        return params

    def _create_wallet_signature(self, signature_parameters: SigParamType) -> str:
        assert self._wallet, "Must provide private_key for endpoints that interact with a wallet"
        fields, values = zip(*signature_parameters)
        signature_parameters_hash: bytes = Web3.solidityKeccak(fields, values)
        signable_message: SignableMessage = encode_defunct(hexstr=signature_parameters_hash.hex())
        signed_message = self._wallet.sign_message(signable_message)  # what type ?
        return signed_message.signature.hex()

    def _create_uri(self, path: str):
        return "{}/{}/{}".format(self.api_url, self.API_VERSION, path)

    def _get_request_kwargs(
        self, path: str, method: str, sign_type: Optional[SignType] = None, **kwargs
    ):

        kwargs["data"] = kwargs.get("data", {})
        kwargs["headers"] = kwargs.get("headers", {})

        # set default requests timeout
        kwargs["timeout"] = 10

        # add our global requests params
        if self._requests_params:
            kwargs.update(self._requests_params)

        if sign_type:
            kwargs["data"]["nonce"] = self._get_nonce()
            if method in ("post", "delete"):
                kwargs["data"] = self._wallet_sign(path, method, kwargs["data"])
            else:
                kwargs["data"]["nonce"] = str(kwargs["data"]["nonce"])
            kwargs["headers"]["IDEX-HMAC-Signature"] = self._sign_params(method, kwargs["data"])

        # if get request assign data array to params value for requests lib
        if kwargs["data"]:
            if method == "get":
                kwargs["params"] = kwargs["data"]
                del kwargs["data"]
            else:
                kwargs["json"] = kwargs["data"]
                del kwargs["data"]

        return kwargs

    def _init_session(self):
        pass

    @property
    def last_response(self):
        """Get the last response object for inspection

        .. code:: python

            response = client.last_response

        :returns: response objects

        """
        return self._last_response

    def faucet_abi(self) -> Dict:
        if not self._faucet_abi:
            with open(Path(__file__).parent / "contracts" / "FaucetToken.abi.json") as fh:
                self._faucet_abi = json.load(fh)
        assert self._faucet_abi
        return self._faucet_abi

    def exchange_abi(self) -> Dict:
        if not self._exchange_abi:
            with open(Path(__file__).parent / "contracts" / "Exchange.abi.json") as fh:
                self._exchange_abi = json.load(fh)
        assert self._exchange_abi
        return self._exchange_abi

    def init_web3_client(self, gas_price_strategy: Callable = rpc_gas_price_strategy):
        w3 = Web3(Web3.HTTPProvider(self.rpc_url))
        w3.middleware_onion.inject(middleware.geth_poa_middleware, layer=0)
        w3.middleware_onion.add(middleware.time_based_cache_middleware)
        w3.middleware_onion.add(middleware.latest_block_based_cache_middleware)
        w3.middleware_onion.add(middleware.simple_cache_middleware)
        w3.eth.set_gas_price_strategy(gas_price_strategy)
        return w3

    def execute_idex_contract_function(
        self,
        function: str,
        function_params: Optional[Iterable] = None,
        tx_params: Optional[Dict] = None,
        tx_options: Optional[TransactionOptions] = None,
    ) -> HexStr:
        contract_params = {
            "address": Web3.toChecksumAddress(self.contracts["exchange"]),
            "abi": self.exchange_abi(),
        }
        return self.execute_contract_function(
            function, contract_params, function_params, tx_params, tx_options
        )

    def execute_exchange_contract_function(
        self,
        function: str,
        contract_address: str,
        function_params: Optional[Iterable] = None,
        tx_params: Optional[Dict] = None,
        tx_options: Optional[TransactionOptions] = None,
    ) -> HexStr:
        contract_params = {
            "address": Web3.toChecksumAddress(contract_address),
            "abi": self.faucet_abi(),
        }
        return self.execute_contract_function(
            function, contract_params, function_params, tx_params, tx_options
        )

    def execute_contract_function(
        self,
        function: str,
        contract_params: Optional[Dict] = None,
        function_params: Optional[Iterable] = None,
        tx_params: Optional[Dict] = None,
        tx_options: Optional[TransactionOptions] = None,
    ) -> HexStr:
        tx_options_dict: Dict = tx_options.to_dict() if tx_options else {}
        w3 = self.init_web3_client()
        contract = w3.eth.contract(**(contract_params or {}))
        txn = getattr(contract.functions, function)(*(function_params or []))
        tx_build_options: Dict[str, Any] = {
            "nonce": w3.eth.get_transaction_count(self.wallet_address),
            **(tx_params or {}),
            **tx_options_dict,
        }
        signed_txn = self.wallet.sign_transaction(txn.buildTransaction(tx_build_options))
        return HexStr(w3.eth.send_raw_transaction(signed_txn.rawTransaction).hex())

    def get_transaction(self, transaction_id: web3_types._Hash32):  # noqa
        w3 = self.init_web3_client()
        return w3.eth.get_transaction(transaction_id)

    def get_transaction_receipt(self, transaction_id: web3_types._Hash32):  # noqa
        w3 = self.init_web3_client()
        return w3.eth.get_transaction_receipt(transaction_id)

    def wait_for_transaction_receipt(
        self,
        transaction_id: web3_types._Hash32,  # noqa
        timeout: int = 120,
        poll_latency: float = 0.1,  # noqa
    ):
        w3 = self.init_web3_client()
        return w3.eth.wait_for_transaction_receipt(
            transaction_id, timeout=timeout, poll_latency=poll_latency
        )

    def _deposit_funds(
        self, asset_details: Dict, quantity: float, tx_options: Optional[TransactionOptions] = None
    ) -> HexStr:

        token_quantity = int(convert_to_token_quantity(asset_details, quantity))

        if asset_details["symbol"] == "MATIC":
            res = self.execute_idex_contract_function(
                function="depositEther",
                function_params=[],
                tx_params={"value": token_quantity},
                tx_options=tx_options,
            )
        else:
            approve_res = self.execute_exchange_contract_function(
                function="approve",
                contract_address=asset_details["contractAddress"],
                function_params=(self.contracts["exchange"], token_quantity),
                tx_options=tx_options,
            )
            self.wait_for_transaction_receipt(approve_res)
            res = self.execute_idex_contract_function(
                function="depositTokenByAddress",
                function_params=(asset_details["contractAddress"], token_quantity),
                tx_options=tx_options,
            )

        return res


class Client(BaseClient):
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        requests_params: Optional[Dict] = None,
        sandbox: bool = False,
    ):
        """

        :param api_key:
        :type api_key: string
        :param api_secret:
        :type api_secret: string
        :param private_key: optional - The private key for the address
        :type private_key: string

        .. code:: python

            # Unauthenticated
            client = Client()

            # Authenticated with API and private key
            api_key = '<api_key>'
            api_secret = '<api_secret>'
            private_key = 'priv_key...'
            client = Client(api_key=api_key, api_secret=api_secret, private_key=private_key)

        """

        super(Client, self).__init__(api_key, api_secret, private_key, requests_params, sandbox)

    def _init_session(self):
        session = requests.session()
        session.headers.update(self._get_headers())
        return session

    def _request(self, method: str, path: str, sign_type: Optional[SignType] = None, **kwargs):

        kwargs = self._get_request_kwargs(path, method, sign_type, **kwargs)
        uri = self._create_uri(path)

        response = getattr(self.session, method)(uri, **kwargs)
        self._last_response = response
        return self._handle_response(response)

    @staticmethod
    def _handle_response(response):
        """Internal helper for handling API responses from the Idex server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status_code).startswith("2"):
            raise IdexAPIException(response, response.status_code, response.text)
        try:
            return response.json()
        except ValueError:
            raise IdexRequestException("Invalid Response: %s" % response.text)

    def _get(self, path, sign_type: Optional[SignType] = None, **kwargs):
        return self._request("get", path, sign_type, **kwargs)

    def _post(self, path, sign_type: Optional[SignType] = None, **kwargs):
        return self._request("post", path, sign_type, **kwargs)

    def _put(self, path, sign_type: Optional[SignType] = None, **kwargs):
        return self._request("put", path, sign_type, **kwargs)

    def _delete(self, path, sign_type: Optional[SignType] = None, **kwargs):
        return self._request("delete", path, sign_type, **kwargs)

    # Public Data Endpoints

    def ping(self):
        """Tests connectivity to the REST API.

        https://api-docs-v3.idex.io/#get-ping

        :returns: API Response

        .. code-block:: python

            {}
        """
        return self._get("ping")

    def get_server_time(self):
        """Returns the current server time.

        https://api-docs-v3.idex.io/#get-time

        :returns: API Response

        .. code-block:: python

            {'serverTime': 1652431505364}
        """
        return self._get("time")

    def get_exchange(self):
        """Returns basic information about the exchange.

        https://api-docs-v3.idex.io/#get-exchange

        :returns: API Response

        .. code-block:: python

            {
                "timeZone": "UTC",
                "serverTime": 1590408000000,
                "maticDepositContractAddress": "0x...",
                "maticCustodyContractAddress": "0x...",
                "maticUsdPrice": "1.46",
                "gasPrice": 7,
                "volume24hUsd": "10416227.98",
                "totalVolumeUsd": "2921007583.74",
                "totalTrades": 5372019,
                "totalValueLockedUsd": "218462011.50",
                "idexTokenAddress": "0x...",
                "idexUsdPrice": "1.62",
                "idexMarketCapUsd": "954070759.33",
                "makerFeeRate": "0.0010",
                "takerFeeRate": "0.0025",
                "takerIdexFeeRate": "0.0005",
                "takerLiquidityProviderFeeRate": "0.0020",
                "makerTradeMinimum": "10.00000000",
                "takerTradeMinimum": "1.00000000",
                "withdrawalMinimum": "0.50000000",
                "liquidityAdditionMinimum": "0.50000000",
                "liquidityRemovalMinimum": "0.40000000",
                "blockConfirmationDelay": 128
            }

        """
        return self._get("exchange")

    def get_assets(self) -> List[Dict]:
        """Returns information about assets supported by the exchange

        https://api-docs-v3.idex.io/#get-assets

        :returns: API Response

        .. code-block:: python

            [
                {
                    "name": "Ether",
                    "symbol": "ETH",
                    "contractAddress": "0x0000000000000000000000000000000000000000",
                    "assetDecimals": 18,
                    "exchangeDecimals": 8,
                    "tokenPrice": "152.67175572"
                },
                {
                    "name": "USD Coin",
                    "symbol": "USDC",
                    "contractAddress": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "assetDecimals": 6,
                    "exchangeDecimals": 8,
                    "tokenPrice": "0.76335877"
                },
                ...
            ]

        """
        return self._get("assets")

    def get_asset(self, asset: str) -> Dict:
        """Get the details for a particular asset using its token name or address

        :param asset: Name of the currency e.g. EOS or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type asset: string or hex string

        .. code:: python

            # using token name
            currency = client.get_asset('USDT')

            # using the address string
            currency = client.get_asset('0xc2132D05D31c914a87C6611C10748AEb04B58e8F')

        :returns:

        .. code-block:: python

            {
                'name': 'Tether',
                'symbol': 'USDT',
                'contractAddress': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
                'assetDecimals': 6,
                'exchangeDecimals': 8,
                'maticPrice': '1.46249520'
            }

        :raises:  IdexCurrencyNotFoundException, IdexResponseException,  IdexAPIException

        """

        if asset not in self._asset_addresses:
            self._asset_addresses = {asset["symbol"]: asset for asset in self.get_assets()}

        res = None
        if asset[:2] == "0x":
            for token, c in self._asset_addresses.items():
                if c["contractAddress"] == asset:
                    res = c
                    break
            if res is None:
                raise IdexCurrencyNotFoundException(asset)
        else:
            if asset not in self._asset_addresses:
                raise IdexCurrencyNotFoundException(asset)
            res = self._asset_addresses[asset]

        return res

    def asset_to_address(self, asset: str):
        """Convert an asset name to an asset contract address"""
        if asset.startswith("0x"):
            return asset
        asset_details = self.get_asset(asset)
        return asset_details["contractAddress"]

    def get_markets(self):
        """Returns information about the currently listed markets.

        https://api-docs-v3.idex.io/#get-markets

        :returns: API Response

        .. code-block:: python

            [
                {
                    "market": "ETH-USDC",
                    "type": "hybrid",
                    "status": "activeHybrid",
                    "baseAsset": "ETH",
                    "baseAssetPrecision": 8,
                    "quoteAsset": "USDC",
                    "quoteAssetPrecision": 8,
                    "makerFeeRate": "0.0010",
                    "takerFeeRate": "0.0025",
                    "takerIdexFeeRate": "0.0005",
                    "takerLiquidityProviderFeeRate": "0.0020"
                },
                ...
            ]
        """
        return self._get("markets")

    # Market Endpoints

    def get_tickers(self, market: Optional[str] = None) -> List[Dict]:
        """Returns market statistics for the trailing 24-hour period.

        https://api-docs-v3.idex.io/#get-tickers

        :returns: API Response

        .. code-block:: python

            [
                {
                    "market": "ETH-USDC",
                    "time": 1590408000000,
                    "open": "202.11928302",
                    "high": "207.58100029",
                    "low": "201.85600392",
                    "close": "206.00192301",
                    "closeQuantity": "9.50000000",
                    "baseVolume": "11297.01959248",
                    "quoteVolume": "2327207.76033252",
                    "percentChange": "1.92",
                    "numTrades": 14201,
                    "ask": "206.00207150",
                    "bid": "206.00084721",
                    "sequence": 848728
                },
                ...
            ]

        """
        data: Dict[str, Any] = {}
        if market:
            data["market"] = market

        return self._get("tickers", data=data)

    def get_ticker(self, market: str) -> Dict:
        """Get ticker for selected market

        https://api-docs-v3.idex.io/#get-tickers

        :returns: API Response

        .. code-block:: python

            {
                "market": "ETH-USDC",
                "time": 1590408000000,
                "open": "202.11928302",
                "high": "207.58100029",
                "low": "201.85600392",
                "close": "206.00192301",
                "closeQuantity": "9.50000000",
                "baseVolume": "11297.01959248",
                "quoteVolume": "2327207.76033252",
                "percentChange": "1.92",
                "numTrades": 14201,
                "ask": "206.00207150",
                "bid": "206.00084721",
                "sequence": 848728
            }

        """

        return self.get_tickers(market)[0]

    def get_candles(
        self,
        market: str,
        interval: CandleInterval,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
    ) -> List[Dict]:
        """Returns candle (OHLCV) data for a market.

        https://api-docs-v3.idex.io/#get-candles

        :returns: API Response

        .. code-block:: python

            [
                {
                    "start": 1590393000000,
                    "open": "202.11928302",
                    "high": "202.98100029",
                    "low": "201.85600392",
                    "close": "202.50192301",
                    "volume": "39.22576247",
                    "sequence": 848678
                },
                ...
            ]
        """
        data: Dict[str, Any] = {"market": market, "interval": interval.value}
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit

        return self._get("candles", data=data)

    def get_trades(
        self,
        market: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ) -> List[Dict]:
        """Returns trade data for a market.

        https://api-docs-v3.idex.io/#get-trades

        :returns: API Response

        .. code-block:: python

            [
                {
                    "fillId": "a0b6a470-a6bf-11ea-90a3-8de307b3b6da",
                    "price": "202.74900000",
                    "quantity": "10.00000000",
                    "quoteQuantity": "2027.49000000",
                    "time": 1590394500000,
                    "makerSide": "sell",
                    "type": "hybrid",
                    "sequence": 848778
                },
                ...
            ]

        """
        data: Dict[str, Any] = {"market": market}
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id

        return self._get("trades", data=data)

    def get_order_book(
        self,
        market: str,
        level: Optional[OrderbookLevel] = OrderbookLevel.LEVEL_1,
        limit: Optional[int] = 50,
        limit_order_only: Optional[bool] = False,
    ):
        """Get order book for selected market

        :returns: Level 1 Response

        .. code-block:: python

            {
                "sequence": 71228121,
                "bids": [
                    [ "202.00200000", "13.88204000", 2 ]
                ],
                "asks": [
                    [ "202.01000000", "8.11400000", 0 ]
                ],
                "pool": {
                    "baseReserveQuantity": "28237.08610815",
                    "quoteReserveQuantity": "5703947.86801900"
                }
            }

        :returns: Level 2 Response

        .. code-block:: python

            {
                "sequence": 71228121,
                "bids": [
                    [ "202.00200000", "13.88204000", 2 ],
                    [ "202.00100000", "8.11411500", 0 ],
                    ...
                ],
                "asks": [
                    [ "202.01000000", "8.11400000", 0 ],
                    [ "202.01100000", "8.11392000", 0 ],
                    ...
                ],
                "pool": {
                    "baseReserveQuantity": "28237.08610815",
                    "quoteReserveQuantity": "5703947.86801900"
                }
            }

        """

        data: Dict[str, Any] = {"market": market}
        if level:
            data["level"] = level.value
        if limit:
            data["limit"] = limit
        if limit_order_only:
            data["limit_order_only"] = True

        return self._get("orderbook", data=data)

    # User Data Endpoints

    def get_account(self):
        """Returns information about the API account.

        :returns: API Response

        .. code-block:: python

            {
                "depositEnabled": true,
                "orderEnabled": true,
                "cancelEnabled": true,
                "withdrawEnabled": true,
                "totalPortfolioValueUsd": "127182.82",
                "makerFeeRate": "0.0010",
                "takerFeeRate": "0.0025",
                "takerIdexFeeRate": "0.0005",
                "takerLiquidityProviderFeeRate": "0.0020"
            }

        """

        return self._get("user", sign_type=SignType.USER)

    def associate_wallet(self, wallet_address: str):
        """Associates a wallet with an API account

        https://api-docs-v3.idex.io/#associate-wallet

        :returns: API Response

        .. code-block:: python

            {
                "address": "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d",
                "totalPortfolioValueUsd": "88141.77",
                "time": 1590393600000
            }

        """

        return self._post("wallets", sign_type=SignType.TRADE, data={"wallet": wallet_address})

    def get_wallets(self):
        """Returns information about the API account.

        :returns: API Response

        .. code-block:: python

            [
                {
                    "address": "0xA71C4aeeAabBBB8D2910F41C2ca3964b81F7310d",
                    "totalPortfolioValueUsd": "88141.77",
                    "time": 1590393600000
                },
                ...
            ]

        """

        return self._get("wallets", sign_type=SignType.USER)

    def get_balances(
        self, wallet_address: Optional[str] = None, assets: Optional[List[str]] = None
    ):
        """Returns asset quantity information held by a wallet on the exchange.

        This endpoint does not include balance information for funds held by a wallet outside the exchange custody
        contract.

        :returns: API Response

        .. code-block:: python

            [
                {
                    "asset": "USDC",
                    "quantity": "38192.94678100",
                    "availableForTrade": "26710.66678121",
                    "locked": "11482.28000000",
                    "usdValue": "38188.22"
                },
                ...
            ]

        """

        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if assets:
            data["asset"] = assets

        return self._get("balances", sign_type=SignType.USER, data=data)

    # Orders & Trade Endpoints

    def create_order(
        self,
        market: str,
        order_type: OrderType,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        client_order_id: Optional[str] = None,
        time_in_force: Optional[OrderTimeInForce] = None,
        self_trade_prevention: Optional[OrderSelfTradePrevention] = None,
        test: Optional[bool] = False,
    ):
        path = "orders"
        if test:
            path = "orders/test"

        if time_in_force == OrderTimeInForce.FILL_OR_KILL:
            assert self_trade_prevention == OrderSelfTradePrevention.CANCEL_NEWEST

        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "market": market,
            "type": order_type.value,
            "side": order_side.value,
        }
        if quantity:
            data["quantity"] = format_quantity(quantity)
        if quote_order_quantity:
            data["quoteOrderQuantity"] = format_quantity(quote_order_quantity)
        if price:
            data["price"] = price
        if stop_price:
            data["stopPrice"] = stop_price
        if client_order_id:
            data["clientOrderId"] = client_order_id
        if time_in_force:
            data["timeInForce"] = time_in_force.value
        if self_trade_prevention:
            data["selfTradePrevention"] = self_trade_prevention.value

        return self._post(path, sign_type=SignType.TRADE, data=data)

    def create_market_order(
        self,
        market: str,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        client_order_id: Optional[str] = None,
        self_trade_prevention: OrderSelfTradePrevention = OrderSelfTradePrevention.DECREMENT_AND_CANCEL,
        test: Optional[bool] = False,
    ):
        return self.create_order(
            market=market,
            order_side=order_side,
            wallet_address=wallet_address,
            quantity=quantity,
            quote_order_quantity=quote_order_quantity,
            client_order_id=client_order_id,
            order_type=OrderType.MARKET,
            self_trade_prevention=self_trade_prevention,
            test=test,
        )

    def create_limit_order(
        self,
        market: str,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        price: Optional[str] = None,
        client_order_id: Optional[str] = None,
        time_in_force: OrderTimeInForce = OrderTimeInForce.GOOD_TILL_CANCEL,
        self_trade_prevention: OrderSelfTradePrevention = OrderSelfTradePrevention.DECREMENT_AND_CANCEL,
        test: Optional[bool] = False,
    ):
        return self.create_order(
            market=market,
            order_side=order_side,
            wallet_address=wallet_address,
            quantity=quantity,
            price=price,
            quote_order_quantity=quote_order_quantity,
            client_order_id=client_order_id,
            order_type=OrderType.LIMIT,
            time_in_force=time_in_force,
            self_trade_prevention=self_trade_prevention,
            test=test,
        )

    def cancel_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
    ):
        """Cancel a single open order, all open orders for a market, or all open orders placed by a wallet.

        https://api-docs-v3.idex.io/?javascript#cancel-order

        :returns: API Response

        .. code-block:: python

            [
                {
                    "orderId": "3a9ef9c0-a779-11ea-907d-23e999279287"
                },
                ...
            ]
        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if order_id:
            data["orderId"] = order_id
        if market:
            data["market"] = market
        return self._delete("orders", sign_type=SignType.TRADE, data=data)

    def cancel_all_orders(self, wallet_address: Optional[str] = None):
        """Cancel all open orders placed by a wallet.

        https://api-docs-v3.idex.io/?javascript#cancel-order

        :returns: API Response

        .. code-block:: python

            [
                {
                    "orderId": "3a9ef9c0-a779-11ea-907d-23e999279287"
                },
                ...
            ]
        """
        return self.cancel_orders(wallet_address=wallet_address)

    def cancel_all_market_orders(self, market: str, wallet_address: Optional[str] = None):
        """Cancel all open orders for a market

        https://api-docs-v3.idex.io/?javascript#cancel-order

        :returns: API Response

        .. code-block:: python

            [
                {
                    "orderId": "3a9ef9c0-a779-11ea-907d-23e999279287"
                },
                ...
            ]
        """
        return self.cancel_orders(wallet_address=wallet_address, market=market)

    def cancel_order(self, order_id: str, wallet_address: Optional[str] = None):
        """Cancel a single open order

        https://api-docs-v3.idex.io/?javascript#cancel-order

        :returns: API Response

        .. code-block:: python

            [
                {
                    "orderId": "3a9ef9c0-a779-11ea-907d-23e999279287"
                },
                ...
            ]
        """
        return self.cancel_orders(wallet_address=wallet_address, order_id=order_id)

    def get_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
        closed: Optional[bool] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about open and past orders.

        https://api-docs-v3.idex.io/?javascript#get-orders

        """

        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if order_id:
            data["orderId"] = order_id
        if market:
            data["market"] = market
        if closed is not None:
            data["closed"] = closed
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return self._get("orders", sign_type=SignType.USER, data=data)

    def get_open_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        self.get_orders(
            wallet_address,
            order_id,
            market,
            closed=False,
            start=start,
            end=end,
            limit=limit,
            from_id=from_id,
        )

    def get_order(self, order_id: str, wallet_address: Optional[str] = None):
        """Returns information about an order

        https://api-docs-v3.idex.io/#get-orders

        """
        return self.get_orders(wallet_address=wallet_address, order_id=order_id)

    def get_fills(
        self,
        wallet_address: Optional[str] = None,
        fill_id: Optional[str] = None,
        market: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about trades involving orders placed by a wallet

        https://api-docs-v3.idex.io/#get-fills

        :returns: API Response

        .. code-block:: python

            [
                {
                    "fillId": "974480d0-a776-11ea-895b-bfcbb5bdaa50",
                    "price": "202.00150000",
                    "quantity": "3.78008801",
                    "quoteQuantity": "763.58344815",
                    "orderBookQuantity": "3.50000000",
                    "orderBookQuoteQuantity": "707.00700000",
                    "poolQuantity": "0.28008801",
                    "poolQuoteQuantity": "56.57644815",
                    "time": 1590394200000,
                    "makerSide": "sell",
                    "sequence": 981372,
                    "market": "ETH-USDC",
                    "orderId": "92782120-a775-11ea-aa55-4da1cc97a06d",
                    "side": "buy",
                    "fee": "0.00756017",
                    "feeAsset": "ETH",
                    "liquidity": "taker",
                    "type": "hybrid",
                    "txId": "0x01d28c33271cf1dd0eb04249617d3092f24bd9bad77ffb57a0316c3ce5425158",
                    "txStatus": "mined"
                },
                ...
            ]

        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if fill_id:
            data["fillId"] = fill_id
        if market:
            data["market"] = market
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return self._get("fills", sign_type=SignType.USER, data=data)

    def get_fill(
        self,
        fill_id: str,
        wallet_address: Optional[str] = None,
    ):
        """Returns information about a trade placed by a wallet

        https://api-docs-v3.idex.io/#get-fills

        """
        return self.get_fills(wallet_address=wallet_address, fill_id=fill_id)

    # deposit endpoints

    def deposit_funds(
        self, asset: str, quantity: float, tx_options: Optional[TransactionOptions] = None
    ) -> HexStr:
        asset_details = self.get_asset(asset)
        return self._deposit_funds(
            asset_details=asset_details, quantity=quantity, tx_options=tx_options
        )

    def get_deposits(
        self,
        wallet_address: Optional[str] = None,
        deposit_id: Optional[str] = None,
        asset: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about deposits made by a wallet.

        https://api-docs-v3.idex.io/#get-deposits

        :returns: API Response

        .. code-block:: python

            [
                {
                    "depositId": "57f88930-a6c7-11ea-9d9c-6b2dc98dcc67",
                    "asset": "USDC",
                    "quantity": "25000.00000000",
                    "txId": "0xf3299b8222b2977fabddcf2d06e2da6303d99c976ed371f9749cb61514078a07",
                    "txTime": 1590393900000,
                    "confirmationTime": 1590394050000
                },
                ...
            ]
        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if deposit_id:
            data["depositId"] = deposit_id
        if asset:
            data["asset"] = asset
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return self._get("fills", sign_type=SignType.USER, data=data)

    def get_deposit(
        self,
        deposit_id: str,
        wallet_address: Optional[str] = None,
    ):
        """Returns information about a deposit made by a wallet.

        https://api-docs-v3.idex.io/#get-deposits
        """

        return self.get_deposits(wallet_address=wallet_address, deposit_id=deposit_id)

    def get_deposit_for_asset(
        self,
        asset: str,
        wallet_address: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about deposits for an asset made by a wallet.

        https://api-docs-v3.idex.io/#get-deposits
        """
        return self.get_deposits(
            wallet_address=wallet_address,
            asset=asset,
            start=start,
            end=end,
            limit=limit,
            from_id=from_id,
        )

    # Withdrawal endpoints

    def withdraw_funds(
        self,
        quantity: float,
        wallet_address: Optional[str] = None,
        asset: Optional[str] = None,
        asset_contract_address: Optional[str] = None,
    ):
        """Withdraw funds from the exchange.

        https://api-docs-v3.idex.io/#withdraw-funds

        :returns: API Response

        .. code-block:: python

            [
                {
                    "withdrawalId": "3ac67790-a77c-11ea-ae39-b3356c7170f3",
                    "asset": "USDC",
                    "assetContractAddress": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "quantity": "25000.00000000",
                    "time": 1590394800000,
                    "fee": "0.14332956",
                    "txId": "0xf215d7a6d20f6dda52cdb3a3332aa5de898dead06f92f4d26523f140ae5dcc5c",
                    "txStatus": "mined"
                },
                ...
            ]

        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "quantity": format_quantity(quantity),
        }
        if asset:
            data["asset"] = asset
        if asset_contract_address:
            data["assetContractAddress"] = asset_contract_address
        return self._post("withdrawals", sign_type=SignType.TRADE, data=data)

    def contract_exit_wallet(self, tx_options: Optional[TransactionOptions] = None):
        """Allow funds to be withdrawn directly from the contract, even if IDEX is offline or otherwise unresponsive

        https://api-docs-v3.idex.io/#exit-wallet

        All future deposits, trades, and liquidity additions and removals are blocked. Any open orders associated with
        the wallet are cleared from the order books, and any liquidity provider (LP) tokens held as exchange balances
        are liquidated.

        Wait at least 1 hour for any in-flight settlement transactions to mine.

        """
        return self.execute_idex_contract_function(function="exitWallet", tx_options=tx_options)

    def contract_withdraw_exit(self, asset: str, tx_options: Optional[TransactionOptions] = None):
        """Transfers the wallet’s full exchange balance of the specified asset back to the wallet

        https://api-docs-v3.idex.io/#exit-wallet

        """
        asset_details = self.get_asset(asset)

        return self.execute_idex_contract_function(
            function="withdrawExit",
            function_params=[asset_details["contractAddress"]],
            tx_options=tx_options,
        )

    def get_withdrawals(
        self,
        wallet_address: Optional[str] = None,
        withdrawal_id: Optional[str] = None,
        asset: Optional[str] = None,
        asset_contract_address: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about withdrawals to a wallet.

        https://api-docs-v3.idex.io/#get-withdrawals

        :returns: API Response

        .. code-block:: python

            [
                {
                    "withdrawalId": "3ac67790-a77c-11ea-ae39-b3356c7170f3",
                    "asset": "USDC",
                    "assetContractAddress": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "quantity": "25000.00000000",
                    "time": 1590394800000,
                    "fee": "0.14332956",
                    "txId": "0xf215d7a6d20f6dda52cdb3a3332aa5de898dead06f92f4d26523f140ae5dcc5c",
                    "txStatus": "mined"
                },
                ...
            ]


        """
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if withdrawal_id:
            data["withdrawalId"] = withdrawal_id
        if asset:
            data["asset"] = asset
        if asset_contract_address:
            data["assetContractAddress"] = asset_contract_address
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id

        return self._get("withdrawals", sign_type=SignType.USER, data=data)

    def get_withdrawal(
        self,
        withdrawal_id: str,
        wallet_address: Optional[str] = None,
    ):
        """Returns information about a withdrawal to a wallet.

        https://api-docs-v3.idex.io/#get-withdrawals

        :returns: API Response

        .. code-block:: python

            [
                {
                    "withdrawalId": "3ac67790-a77c-11ea-ae39-b3356c7170f3",
                    "asset": "USDC",
                    "assetContractAddress": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                    "quantity": "25000.00000000",
                    "time": 1590394800000,
                    "fee": "0.14332956",
                    "txId": "0xf215d7a6d20f6dda52cdb3a3332aa5de898dead06f92f4d26523f140ae5dcc5c",
                    "txStatus": "mined"
                },
                ...
            ]

        """
        return self.get_withdrawals(wallet_address=wallet_address, withdrawal_id=withdrawal_id)

    # Liquidity Endpoints

    def get_liquidity_pools(
        self,
        market: Optional[str] = None,
        token_a: Optional[str] = None,
        token_b: Optional[str] = None,
    ):
        """Returns information about liquidity pools supported by the exchange

        https://api-docs-v3.idex.io/#get-liquidity-pools

        :returns: API Response

        .. code-block:: python

            {
                "tokenA": "0x0000000000000000000000000000000000000000",
                "tokenB": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "reserveA": "28237086108150291001205",
                "reserveB": "5647417229283",
                "liquidityToken": "0x041B70bf48cfF1a7d3E87297D9F13772f11ed764",
                "totalLiquidity": "399332701245168000",
                "reserveUsd": "11294834.44",
                "market": "ETH-USDC"
            }

        """

        data: Dict[str, Any] = {}
        if market:
            data["market"] = market
        if token_a:
            data["tokenA"] = self.asset_to_address(token_a)
        if token_b:
            data["tokenB"] = self.asset_to_address(token_b)
        return self._get("liquidityPools", data=data)

    def add_liquidity(
        self,
        token_a: str,
        token_b: str,
        amount_a: float,
        amount_b: float,
        amount_a_min: float,
        amount_b_min: float,
        to_wallet: str,
        wallet_address: Optional[str] = None,
    ):
        """Add liquidity to a hybrid liquidity pool from assets held by a wallet on the exchange

        https://api-docs-v3.idex.io/#add-liquidity

        :returns: API Response

        .. code-block:: python

            {
                "liquidityAdditionId": "f3fd2683-26e6-4475-88b5-3eeb088acd1f",
                "tokenA": "0x0000000000000000000000000000000000000000",
                "tokenB": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "amountA": "2499999996612190000",
                "amountB": "500000000",
                "liquidity": "35355339001212",
                "time": "1631656966432",
                "initiatingTxId": null,
                "feeTokenA": "1260000000000000",
                "feeTokenB": "252000",
                "txId": "0x39518147124286b97f4803171732aaa1bffea15f12b0474e7ab386bf5cdeda56",
                "txStatus": "mined"
            }

        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "tokenA": self.asset_to_address(token_a),
            "tokenB": self.asset_to_address(token_b),
            "amountADesired": convert_to_token_quantity(self.get_asset(token_a), amount_a),
            "amountBDesired": convert_to_token_quantity(self.get_asset(token_b), amount_b),
            "amountAMin": convert_to_token_quantity(self.get_asset(token_a), amount_a_min),
            "amountBMin": convert_to_token_quantity(self.get_asset(token_b), amount_b_min),
            "to": to_wallet,
        }
        return self._post("addLiquidity", sign_type=SignType.TRADE, data=data)

    def remove_liquidity(
        self,
        token_a: str,
        token_b: str,
        liquidity: float,
        amount_a_min: float,
        amount_b_min: float,
        to_wallet: str,
        wallet_address: Optional[str] = None,
    ):
        """Remove liquidity from a hybrid liquidity pool using liquidity provider (LP) tokens held by a wallet on the
        exchange

        https://api-docs-v3.idex.io/#remove-liquidity

        :returns: API Response

        .. code-block:: python

            {
                "liquidityRemovalId": "e87083db-5f64-4fd8-a1ad-1b57a84840f7",
                "tokenA": "0x0000000000000000000000000000000000000000",
                "tokenB": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                "amountA": "2499999996612190000",
                "amountB": "500000000",
                "liquidity": "35355339001212",
                "time": "1631656967341",
                "initiatingTxId": null,
                "feeTokenA": "1207500000000000",
                "feeTokenB": "241500",
                "txId": "0xfe48b79028a61d971672172874304283aaa6780ad38b9dc2d76c28fe7fd03002",
                "txStatus": "mined"
            }

        """
        token_a_details = self.get_asset(token_a)
        token_b_details = self.get_asset(token_b)
        lp_token_details = self.get_asset(
            f"ILP-{token_a_details['symbol']}-{token_b_details['symbol']}"
        )
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "tokenA": self.asset_to_address(token_a),
            "tokenB": self.asset_to_address(token_b),
            "liquidity": convert_to_token_quantity(lp_token_details, liquidity),
            "amountAMin": convert_to_token_quantity(token_a_details, amount_a_min),
            "amountBMin": convert_to_token_quantity(token_b_details, amount_b_min),
            "to": to_wallet,
        }
        return self._post("removeLiquidity", sign_type=SignType.TRADE, data=data)

    def get_liquidity_additions(
        self,
        wallet_address: Optional[str] = None,
        liquidity_addition_id: Optional[str] = None,
        initiating_tx_id: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about liquidity additions from a wallet.

        https://api-docs-v3.idex.io/?javascript#get-liquidity-additions

        """
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if liquidity_addition_id:
            data["liquidityAdditionId"] = liquidity_addition_id
        if initiating_tx_id:
            data["initiatingTxId"] = initiating_tx_id
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return self._get("liquidityAdditions", sign_type=SignType.USER, data=data)

    def get_liquidity_removals(
        self,
        wallet_address: Optional[str] = None,
        liquidity_removal_id: Optional[str] = None,
        initiating_tx_id: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        """Returns information about liquidity additions from a wallet.

        https://api-docs-v3.idex.io/?javascript#get-liquidity-additions

        """
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if liquidity_removal_id:
            data["liquidityRemovalId"] = liquidity_removal_id
        if initiating_tx_id:
            data["initiatingTxId"] = initiating_tx_id
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return self._get("liquidityRemovals", sign_type=SignType.USER, data=data)

    # Websocket endpoints

    def get_ws_auth_token(self, wallet_address: Optional[str] = None):
        """Returns a single-use authentication token for access to private subscriptions in the WebSocket API.

        https://api-docs-v3.idex.io/#get-authentication-token

        :returns: API Response

        .. code-block:: python

            {
                "token": "<WebSocket authentication token>"
            }

        """
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        return self._get("wsToken", sign_type=SignType.USER, data=data)

    # Contract functions

    def contract_testnet_faucet(self, asset: str):
        asset_details = self.get_asset(asset)
        return self.execute_exchange_contract_function(
            function="faucet",
            contract_address=asset_details["contractAddress"],
            function_params=[self.wallet_address],
        )


class AsyncClient(BaseClient):
    @classmethod
    async def create(
        cls,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        requests_params: Optional[Dict] = None,
        sandbox: bool = False,
    ):

        self = AsyncClient(api_key, api_secret, private_key, requests_params, sandbox)

        return self

    def _init_session(self):

        loop = asyncio.get_event_loop()
        session = aiohttp.ClientSession(loop=loop, headers=self._get_headers())  # type: ignore

        return session

    async def _request(
        self, method: str, path: str, sign_type: Optional[SignType] = None, **kwargs
    ):

        kwargs = self._get_request_kwargs(path, method, sign_type, **kwargs)
        uri = self._create_uri(path)

        async with getattr(self.session, method)(uri, **kwargs) as response:
            self._last_response = response
            return await self._handle_response(response)

    @staticmethod
    async def _handle_response(response):
        """Internal helper for handling API responses from the Quoine server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status).startswith("2"):
            raise IdexAPIException(response, response.status, await response.text())
        try:
            res = await response.json()
            return res
        except ValueError:
            txt = await response.text()
            raise IdexRequestException("Invalid Response: {}".format(txt))

    async def _get(self, path: str, sign_type: Optional[SignType] = None, **kwargs):
        return await self._request("get", path, sign_type, **kwargs)

    async def _post(self, path: str, sign_type: Optional[SignType] = None, **kwargs):
        return await self._request("post", path, sign_type, **kwargs)

    async def _put(self, path: str, sign_type: Optional[SignType] = None, **kwargs):
        return await self._request("put", path, sign_type, **kwargs)

    async def _delete(self, path: str, sign_type: Optional[SignType] = None, **kwargs):
        return await self._request("delete", path, sign_type, **kwargs)

    async def ping(self):
        return await self._get("ping")

    ping.__doc__ = Client.ping.__doc__

    async def get_server_time(self) -> Dict:
        return await self._get("time")

    get_server_time.__doc__ = Client.get_server_time.__doc__

    async def get_exchange(self):
        return await self._get("exchange")

    get_exchange.__doc__ = Client.get_exchange.__doc__

    async def get_assets(self) -> List[Dict]:
        return await self._get("assets")

    get_assets.__doc__ = Client.get_assets.__doc__

    async def get_asset(self, asset: str) -> Dict[str, Any]:
        if asset not in self._asset_addresses:
            self._asset_addresses = {asset["symbol"]: asset for asset in await self.get_assets()}

        res = None
        if asset[:2] == "0x":
            for token, c in self._asset_addresses.items():
                if c["contractAddress"] == asset:
                    res = c
                    break
            if res is None:
                raise IdexCurrencyNotFoundException(asset)
        else:
            if asset not in self._asset_addresses:
                raise IdexCurrencyNotFoundException(asset)
            res = self._asset_addresses[asset]

        return res

    get_asset.__doc__ = Client.get_asset.__doc__

    async def asset_to_address(self, asset: str):
        if asset.startswith("0x"):
            return asset
        asset_details = await self.get_asset(asset)
        return asset_details["contractAddress"]

    asset_to_address.__doc__ = Client.asset_to_address.__doc__

    async def get_markets(self):
        return await self._get("markets")

    get_markets.__doc__ = Client.get_markets.__doc__

    # Market Endpoints

    async def get_tickers(self, market: Optional[str] = None) -> List[Dict]:
        data: Dict[str, Any] = {}
        if market:
            data["market"] = market

        return await self._get("tickers", data=data)

    get_tickers.__doc__ = Client.get_tickers.__doc__

    async def get_ticker(self, market):
        return (await self.get_tickers(market))[0]

    get_ticker.__doc__ = Client.get_ticker.__doc__

    async def get_candles(
        self,
        market: str,
        interval: CandleInterval,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
    ):
        data: Dict[str, Any] = {"market": market, "interval": interval.value}
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit

        return await self._get("candles", data=data)

    get_candles.__doc__ = Client.get_candles.__doc__

    async def get_trades(
        self,
        market: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {"market": market}
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id

        return await self._get("trades", data=data)

    get_trades.__doc__ = Client.get_trades.__doc__

    async def get_order_book(
        self,
        market: str,
        level: Optional[OrderbookLevel] = OrderbookLevel.LEVEL_1,
        limit: Optional[int] = 50,
        limit_order_only: Optional[bool] = False,
    ):
        data: Dict[str, Any] = {"market": market}
        if level:
            data["level"] = level.value
        if limit:
            data["limit"] = limit
        if limit_order_only:
            data["limit_order_only"] = True

        return await self._get("orderbook", data=data)

    get_order_book.__doc__ = Client.get_order_book.__doc__

    # User Data Endpoints

    async def get_account(self):
        return await self._get("user", sign_type=SignType.USER)

    get_account.__doc__ = Client.get_account.__doc__

    async def associate_wallet(self, wallet_address: str):
        return await self._post(
            "wallets", sign_type=SignType.TRADE, data={"wallet": wallet_address}
        )

    associate_wallet.__doc__ = Client.associate_wallet.__doc__

    async def get_wallets(self):
        return await self._get("wallets", sign_type=SignType.USER)

    get_wallets.__doc__ = Client.get_wallets.__doc__

    async def get_balances(
        self, wallet_address: Optional[str] = None, assets: Optional[List[str]] = None
    ):
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if assets:
            data["asset"] = assets

        return await self._get("balances", sign_type=SignType.USER, data=data)

    get_balances.__doc__ = Client.get_balances.__doc__

    # Orders & Trade Endpoints

    async def create_order(
        self,
        market: str,
        order_type: OrderType,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        price: Optional[str] = None,
        stop_price: Optional[str] = None,
        client_order_id: Optional[str] = None,
        time_in_force: Optional[OrderTimeInForce] = None,
        self_trade_prevention: Optional[OrderSelfTradePrevention] = None,
        test: Optional[bool] = False,
    ):
        path = "orders"
        if test:
            path = "orders/test"

        if time_in_force == OrderTimeInForce.FILL_OR_KILL:
            assert self_trade_prevention == OrderSelfTradePrevention.CANCEL_NEWEST

        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "market": market,
            "type": order_type.value,
            "side": order_side.value,
        }
        if quantity:
            data["quantity"] = format_quantity(quantity)
        if quote_order_quantity:
            data["quoteOrderQuantity"] = format_quantity(quote_order_quantity)
        if price:
            data["price"] = price
        if stop_price:
            data["stopPrice"] = stop_price
        if client_order_id:
            data["clientOrderId"] = client_order_id
        if time_in_force:
            data["timeInForce"] = time_in_force.value
        if self_trade_prevention:
            data["selfTradePrevention"] = self_trade_prevention.value

        return await self._post(path, sign_type=SignType.TRADE, data=data)

    create_order.__doc__ = Client.create_order.__doc__

    async def create_market_order(
        self,
        market: str,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        client_order_id: Optional[str] = None,
        self_trade_prevention: OrderSelfTradePrevention = OrderSelfTradePrevention.DECREMENT_AND_CANCEL,
        test: Optional[bool] = False,
    ):
        return await self.create_order(
            market=market,
            order_side=order_side,
            wallet_address=wallet_address,
            quantity=quantity,
            quote_order_quantity=quote_order_quantity,
            client_order_id=client_order_id,
            order_type=OrderType.MARKET,
            self_trade_prevention=self_trade_prevention,
            test=test,
        )

    create_market_order.__doc__ = Client.create_market_order.__doc__

    async def create_limit_order(
        self,
        market: str,
        order_side: OrderSide,
        wallet_address: Optional[str] = None,
        quantity: Optional[Union[float, Decimal]] = None,
        quote_order_quantity: Optional[Union[float, Decimal]] = None,
        price: Optional[str] = None,
        client_order_id: Optional[str] = None,
        time_in_force: OrderTimeInForce = OrderTimeInForce.GOOD_TILL_CANCEL,
        self_trade_prevention: OrderSelfTradePrevention = OrderSelfTradePrevention.DECREMENT_AND_CANCEL,
        test: Optional[bool] = False,
    ):
        return await self.create_order(
            market=market,
            order_side=order_side,
            wallet_address=wallet_address,
            quantity=quantity,
            price=price,
            quote_order_quantity=quote_order_quantity,
            client_order_id=client_order_id,
            order_type=OrderType.LIMIT,
            time_in_force=time_in_force,
            self_trade_prevention=self_trade_prevention,
            test=test,
        )

    create_limit_order.__doc__ = Client.create_limit_order.__doc__

    async def cancel_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
    ):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if order_id:
            data["orderId"] = order_id
        if market:
            data["market"] = market
        return await self._delete("orders", sign_type=SignType.TRADE, data=data)

    cancel_orders.__doc__ = Client.cancel_orders.__doc__

    async def cancel_all_orders(self, wallet_address: Optional[str] = None):
        return self.cancel_orders(wallet_address=wallet_address)

    cancel_all_orders.__doc__ = Client.cancel_all_orders.__doc__

    async def cancel_all_market_orders(self, market: str, wallet_address: Optional[str] = None):
        return await self.cancel_orders(wallet_address=wallet_address, market=market)

    cancel_all_market_orders.__doc__ = Client.cancel_all_market_orders.__doc__

    async def cancel_order(self, order_id: str, wallet_address: Optional[str] = None):
        return await self.cancel_orders(wallet_address=wallet_address, order_id=order_id)

    cancel_order.__doc__ = Client.cancel_order.__doc__

    async def get_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
        closed: Optional[bool] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if order_id:
            data["orderId"] = order_id
        if market:
            data["market"] = market
        if closed is not None:
            data["closed"] = closed
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return await self._get("orders", sign_type=SignType.USER, data=data)

    get_orders.__doc__ = Client.get_orders.__doc__

    async def get_open_orders(
        self,
        wallet_address: Optional[str] = None,
        order_id: Optional[str] = None,
        market: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        return await self.get_orders(
            wallet_address,
            order_id,
            market,
            closed=False,
            start=start,
            end=end,
            limit=limit,
            from_id=from_id,
        )

    get_open_orders.__doc__ = Client.get_open_orders.__doc__

    async def get_order(self, order_id: str, wallet_address: Optional[str] = None):
        return await self.get_orders(wallet_address=wallet_address, order_id=order_id)

    get_order.__doc__ = Client.get_order.__doc__

    async def get_fills(
        self,
        wallet_address: Optional[str] = None,
        fill_id: Optional[str] = None,
        market: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if fill_id:
            data["fillId"] = fill_id
        if market:
            data["market"] = market
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return await self._get("fills", sign_type=SignType.USER, data=data)

    get_fills.__doc__ = Client.get_fills.__doc__

    async def get_fill(
        self,
        fill_id: str,
        wallet_address: Optional[str] = None,
    ):
        return await self.get_fills(wallet_address=wallet_address, fill_id=fill_id)

    get_fill.__doc__ = Client.get_fill.__doc__

    # deposit endpoints

    async def deposit_funds(
        self, asset: str, quantity: float, tx_options: Optional[TransactionOptions] = None
    ) -> HexStr:
        asset_details = await self.get_asset(asset)
        return self._deposit_funds(
            asset_details=asset_details, quantity=quantity, tx_options=tx_options
        )

    deposit_funds.__doc__ = Client.deposit_funds.__doc__

    async def get_deposits(
        self,
        wallet_address: Optional[str] = None,
        deposit_id: Optional[str] = None,
        asset: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        if deposit_id:
            data["depositId"] = deposit_id
        if asset:
            data["asset"] = asset
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return await self._get("fills", sign_type=SignType.USER, data=data)

    get_deposits.__doc__ = Client.get_deposits.__doc__

    async def get_deposit(
        self,
        deposit_id: str,
        wallet_address: Optional[str] = None,
    ):
        return await self.get_deposits(wallet_address=wallet_address, deposit_id=deposit_id)

    get_deposit.__doc__ = Client.get_deposit.__doc__

    async def get_deposit_for_asset(
        self,
        asset: str,
        wallet_address: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        return await self.get_deposits(
            wallet_address=wallet_address,
            asset=asset,
            start=start,
            end=end,
            limit=limit,
            from_id=from_id,
        )

    get_deposit_for_asset.__doc__ = Client.get_deposit_for_asset.__doc__

    # Withdrawal endpoints

    async def withdraw_funds(
        self,
        quantity: float,
        wallet_address: Optional[str] = None,
        asset: Optional[str] = None,
        asset_contract_address: Optional[str] = None,
    ):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "quantity": format_quantity(quantity),
        }
        if asset:
            data["asset"] = asset
        if asset_contract_address:
            data["assetContractAddress"] = asset_contract_address
        return await self._post("withdrawals", sign_type=SignType.TRADE, data=data)

    withdraw_funds.__doc__ = Client.withdraw_funds.__doc__

    async def get_withdrawals(
        self,
        wallet_address: Optional[str] = None,
        withdrawal_id: Optional[str] = None,
        asset: Optional[str] = None,
        asset_contract_address: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if withdrawal_id:
            data["withdrawalId"] = withdrawal_id
        if asset:
            data["asset"] = asset
        if asset_contract_address:
            data["assetContractAddress"] = asset_contract_address
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id

        return await self._get("withdrawals", sign_type=SignType.USER, data=data)

    get_withdrawals.__doc__ = Client.get_withdrawals.__doc__

    async def get_withdrawal(
        self,
        withdrawal_id: str,
        wallet_address: Optional[str] = None,
    ):

        return await self.get_withdrawals(
            wallet_address=wallet_address, withdrawal_id=withdrawal_id
        )

    get_withdrawal.__doc__ = Client.get_withdrawal.__doc__

    # Liquidity Endpoints

    async def get_liquidity_pools(
        self,
        market: Optional[str] = None,
        token_a: Optional[str] = None,
        token_b: Optional[str] = None,
    ):
        data: Dict[str, Any] = {}
        if market:
            data["market"] = market
        if token_a:
            data["tokenA"] = self.asset_to_address(token_a)
        if token_b:
            data["tokenB"] = self.asset_to_address(token_b)
        return await self._get("liquidityPools", data=data)

    get_liquidity_pools.__doc__ = Client.get_liquidity_pools.__doc__

    async def add_liquidity(
        self,
        token_a: str,
        token_b: str,
        amount_a: float,
        amount_b: float,
        amount_a_min: float,
        amount_b_min: float,
        to_wallet: str,
        wallet_address: Optional[str] = None,
    ):
        token_a_details = await self.get_asset(token_a)
        token_b_details = await self.get_asset(token_b)
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "tokenA": await self.asset_to_address(token_a),
            "tokenB": await self.asset_to_address(token_b),
            "amountADesired": convert_to_token_quantity(token_a_details, amount_a),
            "amountBDesired": convert_to_token_quantity(token_b_details, amount_b),
            "amountAMin": convert_to_token_quantity(token_a_details, amount_a_min),
            "amountBMin": convert_to_token_quantity(token_b_details, amount_b_min),
            "to": to_wallet,
        }
        return await self._post("addLiquidity", sign_type=SignType.TRADE, data=data)

    add_liquidity.__doc__ = Client.add_liquidity.__doc__

    async def remove_liquidity(
        self,
        token_a: str,
        token_b: str,
        liquidity: float,
        amount_a_min: float,
        amount_b_min: float,
        to_wallet: str,
        wallet_address: Optional[str] = None,
    ):
        token_a_details = await self.get_asset(token_a)
        token_b_details = await self.get_asset(token_b)
        lp_token_details = await self.get_asset(
            f"ILP-{token_a_details['symbol']}-{token_b_details['symbol']}"
        )
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
            "tokenA": await self.asset_to_address(token_a),
            "tokenB": await self.asset_to_address(token_b),
            "liquidity": convert_to_token_quantity(lp_token_details, liquidity),
            "amountAMin": convert_to_token_quantity(token_a_details, amount_a_min),
            "amountBMin": convert_to_token_quantity(token_b_details, amount_b_min),
            "to": to_wallet,
        }
        return await self._post("removeLiquidity", sign_type=SignType.TRADE, data=data)

    remove_liquidity.__doc__ = Client.remove_liquidity.__doc__

    async def get_liquidity_additions(
        self,
        wallet_address: Optional[str] = None,
        liquidity_addition_id: Optional[str] = None,
        initiating_tx_id: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if liquidity_addition_id:
            data["liquidityAdditionId"] = liquidity_addition_id
        if initiating_tx_id:
            data["initiatingTxId"] = initiating_tx_id
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return await self._get("liquidityAdditions", sign_type=SignType.USER, data=data)

    get_liquidity_additions.__doc__ = Client.get_liquidity_additions.__doc__

    async def get_liquidity_removals(
        self,
        wallet_address: Optional[str] = None,
        liquidity_removal_id: Optional[str] = None,
        initiating_tx_id: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        limit: Optional[int] = 50,
        from_id: Optional[str] = None,
    ):
        data: Dict[str, Any] = {"wallet": wallet_address or self.wallet_address}
        if liquidity_removal_id:
            data["liquidityRemovalId"] = liquidity_removal_id
        if initiating_tx_id:
            data["initiatingTxId"] = initiating_tx_id
        if start:
            data["start"] = start
        if end:
            data["end"] = end
        if limit:
            data["limit"] = limit
        if from_id:
            data["fromId"] = from_id
        return await self._get("liquidityRemovals", sign_type=SignType.USER, data=data)

    get_liquidity_removals.__doc__ = Client.get_liquidity_removals.__doc__

    # Websocket endpoints

    async def get_ws_auth_token(self, wallet_address: Optional[str] = None):
        data: Dict[str, Any] = {
            "wallet": wallet_address or self.wallet_address,
        }
        return await self._get("wsToken", sign_type=SignType.USER, data=data)

    get_ws_auth_token.__doc__ = Client.get_ws_auth_token.__doc__
