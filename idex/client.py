# coding=utf-8

import binascii
import codecs
import re
import requests
import time

from decimal import Decimal

from .exceptions import IdexException, IdexAPIException, IdexRequestException, IdexCurrencyNotFoundException
from .decorators import require_address, require_private_key
from .utils import sha3, ecsign, encode_int32


class BaseClient(object):

    API_URL = 'https://api.idex.market'

    _wallet_address = None
    _private_key = None
    _contract_address = None
    _currency_addresses = {}

    def __init__(self, address=None, private_key=None):
        """IDEX API Client constructor

        Takes an optional wallet address parameter which enables helper functions

        https://github.com/AuroraDAO/idex-api-docs

        :param address: optional - Wallet address
        :type address: address string
        :param private_key: optional - The private key for the address
        :type private_key: string

        .. code:: python

            client = Client()

            # with wallet address and private key
            address = '0x925cfc20de3fcbdba2d6e7c75dbb1d0a3f93b8a3'
            private_key = 'priv_key...'
            client = Client(address, private_key)

        """

        self._start_nonce = None
        self._client_started = int(time.time() * 1000)

        self.session = self._init_session()

    def _get_headers(self):
        return {
            'Accept': 'application/json',
            'User-Agent': 'python-idex'
        }

    def _get_nonce(self):
        """Get a unique nonce for request

        """
        return self._start_nonce + int(time.time() * 1000) - self._client_started

    def _generate_signature(self, data):
        """Generate v, r, s values from payload

        """

        # pack parameters based on type
        sig_str = b''
        for d in data:
            val = d[1]
            if d[2] == 'address':
                # remove 0x prefix and convert to bytes
                val = val[2:].encode('utf-8')
            elif d[2] == 'uint256':
                # encode, pad and convert to bytes
                val = binascii.b2a_hex(encode_int32(int(d[1])))
            sig_str += val

        # hash the packed string
        rawhash = sha3(codecs.decode(sig_str, 'hex_codec'))

        # salt the hashed packed string
        salted = sha3(u"\x19Ethereum Signed Message:\n32".encode('utf-8') + rawhash)

        # sign string
        v, r, s = ecsign(salted, codecs.decode(self._private_key[2:], 'hex_codec'))

        # pad r and s with 0 to 64 places
        return {'v': v, 'r': "{0:#0{1}x}".format(r, 66), 's': "{0:#0{1}x}".format(s, 66)}

    def _create_uri(self, path):
        return '{}/{}'.format(self.API_URL, path)

    def _get_request_kwargs(self, signed, **kwargs):

        kwargs['json'] = kwargs.get('json', {})
        kwargs['headers'] = kwargs.get('headers', {})

        if signed:
            # generate signature e.g. {'v': 28 (or 27), 'r': '0x...', 's': '0x...'}
            kwargs['json'].update(self._generate_signature(kwargs['hash_data']))

            # put hash_data into json param
            for name, value, _param_type in kwargs['hash_data']:
                kwargs['json'][name] = value

            # filter out contract address, not required
            if 'contract_address' in kwargs['json']:
                del (kwargs['json']['contract_address'])

            # remove the passed hash data
            del (kwargs['hash_data'])

        return kwargs

    def _init_session(self):
        pass

    def set_wallet_address(self, address, private_key=None):
        """Set the wallet address. Optionally add the private_key, this is only required for trading.

        :param address: Address of the wallet to use
        :type address: address string
        :param private_key: optional - The private key for the address
        :type private_key: string

        .. code:: python

            client.set_wallet_address('0x925cfc20de3fcbdba2d6e7c75dbb1d0a3f93b8a3', 'priv_key...')

        :returns: nothing

        """
        self._wallet_address = address.lower()
        nonce_res = self.get_my_next_nonce()
        self._start_nonce = nonce_res['nonce']
        if private_key:
            if re.match(r"^0x[0-9a-zA-Z]{64}$", private_key) is None:
                raise(IdexException("Private key in invalid format must satisfy 0x[0-9a-zA-Z]{64}"))
            self._private_key = private_key

    def get_wallet_address(self):
        """Get the wallet address

        .. code:: python

            address = client.get_wallet_address()

        :returns: address string

        """
        return self._wallet_address

    def _num_to_decimal(self, number):
        if type(number) == float:
            number = Decimal(repr(number))
        elif type(number) == int:
            number = Decimal(number)
        elif type(number) == str:
            number = Decimal(number)

        return number

    def _parse_from_currency_quantity(self, currency_details, quantity):
        if currency_details is None:
            return None

        f_q = Decimal(quantity)

        if 'decimals' not in currency_details:
            return f_q

        # divide by currency_details['decimals']
        d_str = "1{}".format(("0" * currency_details['decimals']))
        res = f_q / Decimal(d_str)

        return res

    def _convert_to_currency_quantity(self, currency_details, quantity):
        if currency_details is None:
            return None

        f_q = self._num_to_decimal(quantity)

        if 'decimals' not in currency_details:
            return f_q

        # multiply by currency_details['decimals']
        m_str = "1{}".format(("0" * currency_details['decimals']))
        res = (f_q * Decimal(m_str)).to_integral_exact()

        return str(res)


class Client(BaseClient):

    def __init__(self, address=None, private_key=None):

        super(Client, self).__init__(address, private_key)

        if address:
            self.set_wallet_address(address, private_key)

    def _init_session(self):

        session = requests.session()
        session.headers.update(self._get_headers())
        return session

    def _request(self, method, path, signed, **kwargs):

        kwargs = self._get_request_kwargs(signed, **kwargs)
        uri = self._create_uri(path)

        response = getattr(self.session, method)(uri, **kwargs)
        return self._handle_response(response)

    def _handle_response(self, response):
        """Internal helper for handling API responses from the Quoine server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status_code).startswith('2'):
            raise IdexAPIException(response, response.status_code, response.text)
        try:
            res = response.json()
            if 'error' in res:
                raise IdexAPIException(response, response.status_code, response.text)
            return res
        except ValueError:
            raise IdexRequestException('Invalid Response: %s' % response.text)

    def _get(self, path, signed=False, **kwargs):
        return self._request('get', path, signed, **kwargs)

    def _post(self, path, signed=False, **kwargs):
        return self._request('post', path, signed, **kwargs)

    def _put(self, path, signed=False, **kwargs):
        return self._request('put', path, signed, **kwargs)

    def _delete(self, path, signed=False, **kwargs):
        return self._request('delete', path, signed, **kwargs)

    # Market Endpoints

    def get_tickers(self):
        """Get all market tickers

        Please note: If any field is unavailable due to a lack of trade history or a lack of 24hr data, the field will be set to 'N/A'. percentChange, baseVolume, and quoteVolume will never be 'N/A' but may be 0.

        https://github.com/AuroraDAO/idex-api-docs#returnticker

        .. code:: python

            tickers = client.get_tickers()

        :returns: API Response

        .. code-block:: python

            {
                ETH_SAN:  {
                    last: '0.000981',
                    high: '0.0010763',
                    low: '0.0009777',
                    lowestAsk: '0.00098151',
                    highestBid: '0.0007853',
                    percentChange: '-1.83619353',
                    baseVolume: '7.3922603247161',
                    quoteVolume: '7462.998433'
                },
                ETH_LINK: {
                    last: '0.001',
                    high: '0.0014',
                    low: '0.001',
                    lowestAsk: '0.002',
                    highestBid: '0.001',
                    percentChange: '-28.57142857',
                    baseVolume: '13.651606265667369466',
                    quoteVolume: '9765.891979953083752189'
                }
                # all possible markets follow ...
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        return self._post('returnTicker')

    def get_ticker(self, market):
        """Get ticker for selected market

        Please note: If any field is unavailable due to a lack of trade history or a lack of 24hr data, the field will be set to 'N/A'. percentChange, baseVolume, and quoteVolume will never be 'N/A' but may be 0.

        https://github.com/AuroraDAO/idex-api-docs#returnticker

        :param market: Name of market e.g. ETH_SAN
        :type market: string

        .. code:: python

            ticker = client.get_ticker('ETH_SAN')

        :returns: API Response

        .. code-block:: python

            {
                last: '0.000981',
                high: '0.0010763',
                low: '0.0009777',
                lowestAsk: '0.00098151',
                highestBid: '0.0007853',
                percentChange: '-1.83619353',
                baseVolume: '7.3922603247161',
                quoteVolume: '7462.998433'
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'market': market
        }

        return self._post('returnTicker', False, json=data)

    def get_24hr_volume(self):

        """Get all market tickers

        https://github.com/AuroraDAO/idex-api-docs#return24volume

        .. code:: python

            volume = client.get_24hr_volume()

        :returns: API Response

        .. code-block:: python

            {
                ETH_REP: {
                    ETH: '1.3429046745',
                    REP: '105.29046745'
                },
                ETH_DVIP: {
                    ETH: '4',
                    DVIP: '4'
                },
                totalETH: '5.3429046745'
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        return self._post('return24Volume')

    def get_order_books(self):
        """Get an object of the entire order book keyed by market

        Each market returned will have an asks and bids property containing all the sell orders and buy orders sorted by best price. Order objects will contain a price amount total and orderHash property but also a params property which will contain additional data about the order useful for filling or verifying it.

        https://github.com/AuroraDAO/idex-api-docs#returnorderbook

        .. code:: python

            orderbooks = client.get_order_books()

        :returns: API Response

        .. code-block:: python

            {
                ETH_DVIP: {
                    asks: [
                        {
                            price: '2',
                            amount: '1',
                            total: '2',
                            orderHash: '0x6aee6591def621a435dd86eafa32dfc534d4baa38d715988d6f23f3e2f20a29a',
                            params: {
                                tokenBuy: '0x0000000000000000000000000000000000000000',
                                buySymbol: 'ETH',
                                buyPrecision: 18,
                                amountBuy: '2000000000000000000',
                                tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                                sellSymbol: 'DVIP',
                                sellPrecision: 8,
                                amountSell: '100000000',
                                expires: 190000,
                                nonce: 164,
                                user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                            }
                        }
                    ],
                    bids: [
                        {
                            price: '1',
                            amount: '2',
                            total: '2',
                            orderHash: '0x9ba97cfc6d8e0f9a72e9d26c377be6632f79eaf4d87ac52a2b3d715003b6536e',
                            params: {
                                tokenBuy: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                                buySymbol: 'DVIP',
                                buyPrecision: 8,
                                amountBuy: '200000000',
                                tokenSell: '0x0000000000000000000000000000000000000000',
                                sellSymbol: 'ETH',
                                sellPrecision: 18,
                                amountSell: '2000000000000000000',
                                expires: 190000,
                                nonce: 151,
                                user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                            }
                        }
                    ]
                }
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        return self._post('returnOrderBook')

    def get_order_book(self, market):
        """Get order book for selected market

        Each market returned will have an asks and bids property containing all the sell orders and buy orders sorted by best price. Order objects will contain a price amount total and orderHash property but also a params property which will contain additional data about the order useful for filling or verifying it.

        https://github.com/AuroraDAO/idex-api-docs#returnorderbook

        :param market: Name of market e.g. ETH_SAN
        :type market: string

        .. code:: python

            orderbook = client.get_order_book('ETH_SAN')

        :returns: API Response

        .. code-block:: python

            {
                asks: [
                    {
                        price: '2',
                        amount: '1',
                        total: '2',
                        orderHash: '0x6aee6591def621a435dd86eafa32dfc534d4baa38d715988d6f23f3e2f20a29a',
                        params: {
                            tokenBuy: '0x0000000000000000000000000000000000000000',
                            buySymbol: 'ETH',
                            buyPrecision: 18,
                            amountBuy: '2000000000000000000',
                            tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                            sellSymbol: 'DVIP',
                            sellPrecision: 8,
                            amountSell: '100000000',
                            expires: 190000,
                            nonce: 164,
                            user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                        }
                    }
                ],
                bids: [
                    {
                        price: '1',
                        amount: '2',
                        total: '2',
                        orderHash: '0x9ba97cfc6d8e0f9a72e9d26c377be6632f79eaf4d87ac52a2b3d715003b6536e',
                        params: {
                            tokenBuy: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                            buySymbol: 'DVIP',
                            buyPrecision: 8,
                            amountBuy: '200000000',
                            tokenSell: '0x0000000000000000000000000000000000000000',
                            sellSymbol: 'ETH',
                            sellPrecision: 18,
                            amountSell: '2000000000000000000',
                            expires: 190000,
                            nonce: 151,
                            user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                        }
                    }
                ]
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'market': market
        }

        return self._post('returnOrderBook', False, json=data)

    def get_open_orders(self, market, address):
        """Get the open orders for a given market and address

        Output is similar to the output for get_order_book() except that orders are not sorted by type or price, but are rather displayed in the order of insertion. As is the case with get_order_book( there is a params property of the response value that contains details on the order which can help with verifying its authenticity.

        https://github.com/AuroraDAO/idex-api-docs#returnopenorders

        :param market: Name of market e.g. ETH_SAN
        :type market: string
        :param address: Address to return open orders associated with
        :type address: address string

        .. code:: python

            orders = client.get_open_orders(
                'ETH_SAN',
                '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63')

        :returns: API Response

        .. code-block:: python

            [
                {
                    orderNumber: 1412,
                    orderHash: '0xf1bbc500af8d411b0096ac62bc9b60e97024ad8b9ea170340ff0ecfa03536417',
                    price: '2.3',
                    amount: '1.2',
                    total: '2.76',
                    type: 'sell',
                    params: {
                        tokenBuy: '0x0000000000000000000000000000000000000000',
                        buySymbol: 'ETH',
                        buyPrecision: 18,
                        amountBuy: '2760000000000000000',
                        tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                        sellSymbol: 'DVIP',
                        sellPrecision: 8,
                        amountSell: '120000000',
                        expires: 190000,
                        nonce: 166,
                        user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                    }
                },
                {
                    orderNumber: 1413,
                    orderHash: '0x62748b55e1106f3f453d51f9b95282593ef5ce03c22f3235536cf63a1476d5e4',
                    price: '2.98',
                    amount: '1.2',
                    total: '3.576',
                    type: 'sell',
                    params:{
                        tokenBuy: '0x0000000000000000000000000000000000000000',
                        buySymbol: 'ETH',
                        buyPrecision: 18,
                        amountBuy: '3576000000000000000',
                        tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                        sellSymbol: 'DVIP',
                        sellPrecision: 8,
                        amountSell: '120000000',
                        expires: 190000,
                        nonce: 168,
                        user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                    }
                }
            ]

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'market': market,
            'address': address
        }

        return self._post('returnOpenOrders', False, json=data)

    @require_address
    def get_my_open_orders(self, market):
        """Get your open orders for a given market

        Output is similar to the output for get_order_book() except that orders are not sorted by type or price, but are rather displayed in the order of insertion. As is the case with get_order_book( there is a params property of the response value that contains details on the order which can help with verifying its authenticity.

        https://github.com/AuroraDAO/idex-api-docs#returnopenorders

        :param market: Name of market e.g. ETH_SAN
        :type market: string

        .. code:: python

            orders = client.get_my_open_orders('ETH_SAN')

        :returns: API Response

        .. code-block:: python

            [
                {
                    orderNumber: 1412,
                    orderHash: '0xf1bbc500af8d411b0096ac62bc9b60e97024ad8b9ea170340ff0ecfa03536417',
                    price: '2.3',
                    amount: '1.2',
                    total: '2.76',
                    type: 'sell',
                    params: {
                        tokenBuy: '0x0000000000000000000000000000000000000000',
                        buySymbol: 'ETH',
                        buyPrecision: 18,
                        amountBuy: '2760000000000000000',
                        tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                        sellSymbol: 'DVIP',
                        sellPrecision: 8,
                        amountSell: '120000000',
                        expires: 190000,
                        nonce: 166,
                        user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                    }
                },
                {
                    orderNumber: 1413,
                    orderHash: '0x62748b55e1106f3f453d51f9b95282593ef5ce03c22f3235536cf63a1476d5e4',
                    price: '2.98',
                    amount: '1.2',
                    total: '3.576',
                    type: 'sell',
                    params:{
                        tokenBuy: '0x0000000000000000000000000000000000000000',
                        buySymbol: 'ETH',
                        buyPrecision: 18,
                        amountBuy: '3576000000000000000',
                        tokenSell: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                        sellSymbol: 'DVIP',
                        sellPrecision: 8,
                        amountSell: '120000000',
                        expires: 190000,
                        nonce: 168,
                        user: '0xca82b7b95604f70b3ff5c6ede797a28b11b47d63'
                    }
                }
            ]

        :raises:  IdexWalletAddressNotFoundException, IdexResponseException,  IdexAPIException

        """

        return self.get_open_orders(market, self._wallet_address)

    def get_trade_history(self, market=None, address=None, start=None, end=None):
        """Get the past 200 trades for a given market and address, or up to 10000 trades between a range specified in UNIX timetsamps by the "start" and "end" properties of your JSON input.

        https://github.com/AuroraDAO/idex-api-docs#returntradehistory

        :param market: optional - will return an array of trade objects for the market, if omitted, will return an object of arrays of trade objects keyed by each market
        :type market: string
        :param address: optional - If specified, return value will only include trades that involve the address as the maker or taker.
        :type address: address string
        :param start: optional - The inclusive UNIX timestamp (seconds since epoch) marking the earliest trade that will be returned in the response, (Default - 0)
        :type start: int
        :param end: optional - The inclusive UNIX timestamp marking the latest trade that will be returned in the response. (Default - current timestamp)
        :type end: int

        .. code:: python

            trades = client.get_trade_history()

            # get trades for the last 2 hours for ETH EOS market
            start = int(time.time()) - (60 * 2) # 2 hours ago
            trades = client.get_trade_history(market='ETH_EOS', start=start)

        :returns: API Response

        .. code-block:: python

            {
                ETH_REP: [
                    {
                        date: '2017-10-11 21:41:15',
                        amount: '0.3',
                        type: 'buy',
                        total: '1',
                        price: '0.3',
                        orderHash: '0x600c405c44d30086771ac0bd9b455de08813127ff0c56017202c95df190169ae',
                        uuid: 'e8719a10-aecc-11e7-9535-3b8451fd4699',
                        transactionHash: '0x28b945b586a5929c69337929533e04794d488c2d6e1122b7b915705d0dff8bb6'
                    }
                ]
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {}
        if market:
            data['market'] = market
        if address:
            data['address'] = address
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        return self._post('returnTradeHistory', False, json=data)

    @require_address
    def get_my_trade_history(self, market=None, start=None, end=None):
        """Get your past 200 trades for a given market, or up to 10000 trades between a range specified in UNIX timetsamps by the "start" and "end" properties of your JSON input.

        https://github.com/AuroraDAO/idex-api-docs#returntradehistory

        :param market: optional - will return an array of trade objects for the market, if omitted, will return an object of arrays of trade objects keyed by each market
        :type market: string
        :param address: optional - If specified, return value will only include trades that involve the address as the maker or taker.
        :type address: address string
        :param start: optional - The inclusive UNIX timestamp (seconds since epoch) marking the earliest trade that will be returned in the response, (Default - 0)
        :type start: int
        :param end: optional - The inclusive UNIX timestamp marking the latest trade that will be returned in the response. (Default - current timestamp)
        :type end: int

        .. code:: python

            trades = client.get_my_trade_history()

            # get trades for the last 2 hours for ETH EOS market
            start = int(time.time()) - (60 * 2) # 2 hours ago
            trades = client.get_my_trade_history(market='ETH_EOS', start=start)

        :returns: API Response

        .. code-block:: python

            {
                ETH_REP: [
                    {
                        date: '2017-10-11 21:41:15',
                        amount: '0.3',
                        type: 'buy',
                        total: '1',
                        price: '0.3',
                        orderHash: '0x600c405c44d30086771ac0bd9b455de08813127ff0c56017202c95df190169ae',
                        uuid: 'e8719a10-aecc-11e7-9535-3b8451fd4699',
                        transactionHash: '0x28b945b586a5929c69337929533e04794d488c2d6e1122b7b915705d0dff8bb6'
                    }
                ]
            }

        :raises:  IdexWalletAddressNotFoundException, IdexResponseException,  IdexAPIException

        """

        return self.get_trade_history(market, self._wallet_address, start, end)

    def get_currencies(self):
        """Get token data indexed by symbol

        https://github.com/AuroraDAO/idex-api-docs#returncurrencies

        .. code:: python

            currencies = client.get_currencies()

        :returns: API Response

        .. code-block:: python

            {
                ETH: {
                    decimals: 18,
                    address: '0x0000000000000000000000000000000000000000',
                    name: 'Ether'
                },
                REP: {
                    decimals: 8,
                    address: '0xc853ba17650d32daba343294998ea4e33e7a48b9',
                    name: 'Reputation'
                },
                DVIP: {
                    decimals: 8,
                    address: '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
                    name: 'Aurora'
                }
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        return self._post('returnCurrencies')

    def get_currency(self, currency):
        """Get the details for a particular currency using it's token name or address

        :param currency: Name of the currency e.g. EOS or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type currency: string or hex string

        .. code:: python

            # using token name
            currency = client.get_currency('REP')

            # using the address string
            currency = client.get_currency('0xc853ba17650d32daba343294998ea4e33e7a48b9')

        :returns:

        .. code-block:: python

            {
                decimals: 8,
                address: '0xc853ba17650d32daba343294998ea4e33e7a48b9',
                name: 'Reputation'
            }

        :raises:  IdexCurrencyNotFoundException, IdexResponseException,  IdexAPIException

        """

        if currency not in self._currency_addresses:
            self._currency_addresses = self.get_currencies()

        res = None
        if currency[:2] == '0x':
            for token, c in self._currency_addresses.items():
                if c['address'] == currency:
                    res = c
                    break
            # check if we found the currency
            if res is None:
                raise IdexCurrencyNotFoundException(currency)
        else:
            if currency not in self._currency_addresses:
                raise IdexCurrencyNotFoundException(currency)
            res = self._currency_addresses[currency]

        return res

    def get_balances(self, address, complete=False):
        """Get available balances for an address (total deposited minus amount in open orders) indexed by token symbol.

        https://github.com/AuroraDAO/idex-api-docs#returnbalances

        :param address: Address to query balances of
        :type address: address string
        :param complete: Include available balances along with the amount you have in open orders for each token (Default False)
        :param complete: bool

        .. code:: python

            balances = client.get_balances('0xca82b7b95604f70b3ff5c6ede797a28b11b47d63')

        :returns: API Response

        .. code-block:: python

            # Without complete details
            {
                REP: '25.55306545',
                DVIP: '200000000.31012358'
            }

            # With complete details
            {
                REP: {
                    available: '25.55306545',
                    onOrders: '0'
                },
                DVIP: {
                    available: '200000000.31012358',
                    onOrders: '0'
                }
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'address': address
        }

        path = 'returnBalances'
        if complete:
            path = 'returnCompleteBalances'

        return self._post(path, False, json=data)

    @require_address
    def get_my_balances(self, complete=False):
        """Get your available balances (total deposited minus amount in open orders) indexed by token symbol.

        https://github.com/AuroraDAO/idex-api-docs#returnbalances

        :param complete: Include available balances along with the amount you have in open orders for each token (Default False)
        :param complete: bool

        .. code:: python

            balances = client.get_my_balances()

        :returns: API Response

        .. code-block:: python

            # Without complete details
            {
                REP: '25.55306545',
                DVIP: '200000000.31012358'
            }

            # With complete details
            {
                REP: {
                    available: '25.55306545',
                    onOrders: '0'
                },
                DVIP: {
                    available: '200000000.31012358',
                    onOrders: '0'
                }
            }

        :raises:  IdexWalletAddressNotFoundException, IdexResponseException,  IdexAPIException

        """

        return self.get_balances(self._wallet_address, complete)

    def get_transfers(self, address, start=None, end=None):
        """Returns the deposit and withdrawal history for an address within a range, specified by the "start" and "end" properties of the JSON input, both of which must be UNIX timestamps. Withdrawals can be marked as "PENDING" if they are queued for dispatch, "PROCESSING" if the transaction has been dispatched, and "COMPLETE" if the transaction has been mined.

        https://github.com/AuroraDAO/idex-api-docs#returndepositswithdrawals

        :param address: Address to query deposit/withdrawal history for
        :type address: address string
        :param start: optional - Inclusive starting UNIX timestamp of returned results (Default - 0)
        :type start: int
        :param end: optional -  Inclusive ending UNIX timestamp of returned results (Default - current timestamp)
        :type end: int

        .. code:: python

            transfers = client.get_transfers('0xca82b7b95604f70b3ff5c6ede797a28b11b47d63')

        :returns: API Response

        .. code-block:: python

            {
                deposits: [
                    {
                        depositNumber: 265,
                        currency: 'ETH',
                        amount: '4.5',
                        timestamp: 1506550595,
                        transactionHash: '0x52897291dba0a7b255ee7a27a8ca44a9e8d6919ca14f917616444bf974c48897'
                    }
                ],
                withdrawals: [
                    {
                        withdrawalNumber: 174,
                        currency: 'ETH',
                        amount: '4.5',
                        timestamp: 1506552152,
                        transactionHash: '0xe52e9c569fe659556d1e56d8cca2084db0b452cd889f55ec3b4e2f3af61faa57',
                        status: 'COMPLETE'
                    }
                ]
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'address': address
        }
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        return self._post('returnDepositsWithdrawals', False, json=data)

    @require_address
    def get_my_transfers(self, start=None, end=None):
        """Returns your deposit and withdrawal history within a range, specified by the "start" and "end" properties of the JSON input, both of which must be UNIX timestamps. Withdrawals can be marked as "PENDING" if they are queued for dispatch, "PROCESSING" if the transaction has been dispatched, and "COMPLETE" if the transaction has been mined.

        https://github.com/AuroraDAO/idex-api-docs#returndepositswithdrawals

        :param start: optional - Inclusive starting UNIX timestamp of returned results (Default - 0)
        :type start: int
        :param end: optional -  Inclusive ending UNIX timestamp of returned results (Default - current timestamp)
        :type end: int

        .. code:: python

            transfers = client.get_transfers('0xca82b7b95604f70b3ff5c6ede797a28b11b47d63')

        :returns: API Response

        .. code-block:: python

            {
                deposits: [
                    {
                        depositNumber: 265,
                        currency: 'ETH',
                        amount: '4.5',
                        timestamp: 1506550595,
                        transactionHash: '0x52897291dba0a7b255ee7a27a8ca44a9e8d6919ca14f917616444bf974c48897'
                    }
                ],
                withdrawals: [
                    {
                        withdrawalNumber: 174,
                        currency: 'ETH',
                        amount: '4.5',
                        timestamp: 1506552152,
                        transactionHash: '0xe52e9c569fe659556d1e56d8cca2084db0b452cd889f55ec3b4e2f3af61faa57',
                        status: 'COMPLETE'
                    }
                ]
            }

        :raises:  IdexWalletAddressNotFoundException, IdexResponseException,  IdexAPIException

        """

        return self.get_transfers(self._wallet_address, start, end)

    def get_order_trades(self, order_hash):
        """Get all trades involving a given order hash, specified by the order_hash

        https://github.com/AuroraDAO/idex-api-docs#returnordertrades

        :param order_hash: The order hash to query for associated trades
        :type order_hash: 256-bit hex string

        .. code:: python

            trades = client.get_order_trades('0x62748b55e1106f3f453d51f9b95282593ef5ce03c22f3235536cf63a1476d5e4')

        :returns: API Response

        .. code-block:: python

            [
                {
                    date: '2017-10-11 21:41:15',
                    amount: '0.3',
                    type: 'buy',
                    total: '1',
                    price: '0.3',
                    uuid: 'e8719a10-aecc-11e7-9535-3b8451fd4699',
                    transactionHash: '0x28b945b586a5929c69337929533e04794d488c2d6e1122b7b915705d0dff8bb6'
                }
            ]

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'orderHash': order_hash
        }

        return self._post('returnOrderTrades', False, json=data)

    def get_next_nonce(self, address):
        """Get the lowest nonce that you can use from the given address in one of the trade functions

        https://github.com/AuroraDAO/idex-api-docs#returnnextnonce

        :param address: The address to query for the next nonce to use
        :type address: address string

        .. code:: python

            nonce = client.get_next_nonce('0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c')

        :returns: API Response

        .. code-block:: python

            {
                nonce: 2650
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        data = {
            'address': address
        }

        return self._post('returnNextNonce', False, json=data)

    @require_address
    def get_my_next_nonce(self):
        """Get the lowest nonce that you can use in one of the trade functions

        https://github.com/AuroraDAO/idex-api-docs#returnnextnonce

        .. code:: python

            nonce = client.get_next_nonce('0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c')

        :returns: API Response

        .. code-block:: python

            {
                nonce: 2650
            }

        :raises:  IdexWalletAddressNotFoundException, IdexResponseException,  IdexAPIException

        """

        return self.get_next_nonce(self._wallet_address)

    def _get_contract_address(self):
        """Get a cached contract address value

        """
        if not self._contract_address:
            res = self.get_contract_address()
            self._contract_address = res['address']

        return self._contract_address

    def get_contract_address(self):
        """Get the contract address used for depositing, withdrawing, and posting orders

        https://github.com/AuroraDAO/idex-api-docs#returncontractaddress

        .. code:: python

            trades = client.get_contract_address()

        :returns: API Response

        .. code-block:: python

            {
                address: '0x2a0c0dbecc7e4d658f48e01e3fa353f44050c208'
            }

        :raises:  IdexResponseException,  IdexAPIException

        """

        return self._post('returnContractAddress')

    # Trade Endpoints

    def parse_from_currency_quantity(self, currency, quantity):
        """Convert a quantity string to a float

        :param currency: Name of currency e.g EOS
        :type currency: string
        :param quantity: Quantity value as string '3100000000000000000000'
        :type quantity: string

        :returns: decimal

        """

        currency_details = self.get_currency(currency)

        return self._parse_from_currency_quantity(currency_details, quantity)

    def convert_to_currency_quantity(self, currency, quantity):
        """Convert a float quantity to the correct decimal places

        :param currency: Name or address of currency e.g EOS or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type currency: string
        :param quantity: Quantity value 4.234298924 prefer Decimal or string, int or float should work
        :type quantity: Decimal, string, int, float

        """
        currency_details = self.get_currency(currency)

        return self._convert_to_currency_quantity(currency_details, quantity)

    @require_address
    def create_order(self, token_buy, token_sell, price, quantity):
        """Create a limit order

        :param token_buy: The name or address of the token you will receive as a result of the trade e.g. ETH or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type token_buy: string
        :param token_sell:  The name or address of the token you will lose as a result of the trade e.g. EOS or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type token_sell: string
        :param price:  The price in token_sell you want to purchase the new token for
        :type price: Decimal, string, int or float
        :param quantity: The amount of token_buy you will receive when the order is fully filled
        :type quantity: Decimal, string, int or float

        .. code:: python

            ticker = client.create_order(
                'EOS',
                'ETH',
                '0.000123',
                '31200.324')

        :returns: API Response

        .. code-block:: python

            {
                orderNumber: 2101,
                orderHash: '0x3fe808be7b5df3747e5534056e9ff45ead5b1fcace430d7b4092e5fcd7161e21',
                price: '0.000129032258064516',
                amount: '3100',
                total: '0.4',
                type: 'buy',
                params: {
                    tokenBuy: '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098',
                    buyPrecision: 18,
                    amountBuy: '3100000000000000000000',
                    tokenSell: '0x0000000000000000000000000000000000000000',
                    sellPrecision: 18,
                    amountSell: '400000000000000000',
                    expires: 100000,
                    nonce: 1,
                    user: '0x57b080554ebafc8b17f4a6fd090c18fc8c9188a0'
                }
            }

        :raises:  IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException, IdexResponseException,  IdexAPIException

        """

        # convert buy and sell amounts based on decimals
        price = self._num_to_decimal(price)
        quantity = self._num_to_decimal(quantity)
        sell_quantity = price * quantity
        amount_buy = self.convert_to_currency_quantity(token_buy, quantity)
        amount_sell = self.convert_to_currency_quantity(token_sell, sell_quantity)

        return self.create_order_wei(token_buy, token_sell, amount_buy, amount_sell)

    @require_address
    @require_private_key
    def create_order_wei(self, token_buy, token_sell, amount_buy, amount_sell):
        """Create a limit order using buy and sell amounts as integer value precision matching that token

        :param token_buy: The name or address of the token you will receive as a result of the trade e.g. ETH or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type token_buy: string
        :param token_sell:  The name or address of the token you will lose as a result of the trade e.g. EOS or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :type token_sell: string
        :param amount_buy:  The amount of token_buy you will receive when the order is fully filled
        :type amount_buy: Decimal, string
        :param amount_sell: The amount of token_sell you are selling
        :type amount_sell: Decimal, string

        .. code:: python

            ticker = client.create_order_gwei(
                'EOS',
                'ETH',
                '3100000000000000000000',
                '400000000000000000')

        :returns: API Response

        .. code-block:: python

            {
                orderNumber: 2101,
                orderHash: '0x3fe808be7b5df3747e5534056e9ff45ead5b1fcace430d7b4092e5fcd7161e21',
                price: '0.000129032258064516',
                amount: '3100',
                total: '0.4',
                type: 'buy',
                params: {
                    tokenBuy: '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098',
                    buyPrecision: 18,
                    amountBuy: '3100000000000000000000',
                    tokenSell: '0x0000000000000000000000000000000000000000',
                    sellPrecision: 18,
                    amountSell: '400000000000000000',
                    expires: 100000,
                    nonce: 1,
                    user: '0x57b080554ebafc8b17f4a6fd090c18fc8c9188a0'
                }
            }

        :raises:  IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException, IdexResponseException,  IdexAPIException

        """

        contract_address = self._get_contract_address()

        buy_currency = self.get_currency(token_buy)
        sell_currency = self.get_currency(token_sell)

        hash_data = [
            ['contractAddress', contract_address, 'address'],
            ['tokenBuy', buy_currency['address'], 'address'],
            ['amountBuy', amount_buy, 'uint256'],
            ['tokenSell', sell_currency['address'], 'address'],
            ['amountSell', amount_sell, 'uint256'],
            ['expires', '10000', 'uint256'],
            ['nonce', self._get_nonce(), 'uint256'],
            ['address', self._wallet_address, 'address'],
        ]

        return self._post('order', True, hash_data=hash_data)

    @require_address
    @require_private_key
    def create_trade(self, order_hash, token, amount):
        """Make a trade

        TODO: Allow multiple orders to be filled

        :param order_hash: This is the raw hash of the order you are filling. The orderHash property of an order can be retrieved from the API calls which return orders, for higher security the has can be derived from the order parameters.
        :type order_hash: string e.g ‘0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52’
        :param token: The name or address of the token you are filling the order with. In the order it's the tokenBuy token
        :type token: string or hex string e.g 'EOS' or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'
        :param amount: This is the amount of the order you are filling  e.g 0.2354
        :type amount: Decimal, string, int or float

        .. code:: python

            trades = client.create_trade(
                '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52',
                'ETH',
                '1.23')

        :returns: API Response

        .. code-block:: python

            [
                {
                    amount: '0.07',
                    date: '2017-10-13 16:25:36',
                    total: '0.01',
                    market: 'ETH_DVIP',
                    type: 'buy',
                    price: '7',
                    orderHash: '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52',
                    uuid: '250d51a0-b033-11e7-9984-a9ab79bb8f35'
                }
            ]

        :raises:  IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException, IdexResponseException,  IdexAPIException

        """

        amount_trade = self.convert_to_currency_quantity(token, amount)

        hash_data = [
            ['orderHash', order_hash, 'address'],
            ['amount', amount_trade, 'uint256'],
            ['address', self._wallet_address, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        return self._post('trade', True, hash_data=hash_data)

    @require_address
    @require_private_key
    def cancel_order(self, order_hash):
        """Cancel an order

        :param order_hash: The raw hash of the order you are cancelling
        :type order_hash:

        .. code:: python

            status = client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

        :returns: API Response

        .. code-block:: python

            {
                success: 1
            }

        :raises:  IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException, IdexResponseException,  IdexAPIException

        """

        hash_data = [
            ['orderHash', order_hash, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        json_data = {
            'address': self._wallet_address
        }

        return self._post('cancel', True, hash_data=hash_data, json=json_data)

    # Withdraw Endpoints

    @require_address
    @require_private_key
    def withdraw(self, amount, token):
        """Withdraw funds from IDEX to your wallet address

        :param amount:  The amount of token you want to withdraw
        :type amount: Decimal, string
        :param token: The name or address of the token you are withdrawing. In the order it's the tokenBuy token
        :type token: string or hex string e.g 'EOS' or '0x7c5a0ce9267ed19b22f8cae653f198e3e8daf098'

        .. code:: python

            status = client.withdraw('1000.32', 'EOS')

        :returns: API Response

        :raises:  IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException, IdexResponseException,  IdexAPIException

        """

        contract_address = self._get_contract_address()

        currency = self.get_currency(token)

        # convert amount
        amount = self.convert_to_currency_quantity(token, amount)

        hash_data = [
            ['contractAddress', contract_address, 'address'],
            ['token', currency['address'], 'address'],
            ['amount', amount, 'uint256'],
            ['address', self._wallet_address, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        return self._post('withdraw', True, hash_data=hash_data)
