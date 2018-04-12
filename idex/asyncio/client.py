import aiohttp
import asyncio
import re

from idex.client import BaseClient, Client
from idex.exceptions import IdexException, IdexAPIException, IdexRequestException, IdexCurrencyNotFoundException
from idex.decorators import require_address, require_private_key


class AsyncClient(BaseClient):

    @classmethod
    async def create(cls, address=None, private_key=None):

        self = AsyncClient(address, private_key)

        if address:
            await self.set_wallet_address(address, private_key)

        return self

    def _init_session(self):

        loop = asyncio.get_event_loop()
        session = aiohttp.ClientSession(
            loop=loop,
            headers=self._get_headers()
        )

        return session

    async def _request(self, method, path, signed, **kwargs):

        kwargs = self._get_request_kwargs(signed, **kwargs)
        uri = self._create_uri(path)

        async with getattr(self.session, method)(uri, **kwargs) as response:
            return await self._handle_response(response)

    async def _handle_response(self, response):
        """Internal helper for handling API responses from the Quoine server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status).startswith('2'):
            raise IdexAPIException(response, response.status, await response.text())
        try:
            res = await response.json()
            if 'error' in res:
                raise IdexAPIException(response, response.status, await response.text())
            return res
        except ValueError:
            txt = await response.text()
            raise IdexRequestException('Invalid Response: {}'.format(txt))

    async def _get(self, path, signed=False, **kwargs):
        return await self._request('get', path, signed, **kwargs)

    async def _post(self, path, signed=False, **kwargs):
        return await self._request('post', path, signed, **kwargs)

    async def _put(self, path, signed=False, **kwargs):
        return await self._request('put', path, signed, **kwargs)

    async def _delete(self, path, signed=False, **kwargs):
        return await self._request('delete', path, signed, **kwargs)

    async def set_wallet_address(self, address, private_key=None):
        self._wallet_address = address.lower()
        nonce_res = await self.get_my_next_nonce()
        self._start_nonce = nonce_res['nonce']
        if private_key:
            if re.match(r"^0x[0-9a-zA-Z]{64}$", private_key) is None:
                raise(IdexException("Private key in invalid format must satisfy 0x[0-9a-zA-Z]{64}"))
            self._private_key = private_key
    set_wallet_address.__doc__ = Client.set_wallet_address.__doc__

    # Market Endpoints

    async def get_tickers(self):
        return await self._post('returnTicker')
    get_tickers.__doc__ = Client.get_tickers.__doc__

    async def get_ticker(self, market):
        data = {
            'market': market
        }
        return await self._post('returnTicker', False, json=data)
    get_ticker.__doc__ = Client.get_ticker.__doc__

    async def get_24hr_volume(self):
        return await self._post('return24Volume')
    get_24hr_volume.__doc__ = Client.get_24hr_volume.__doc__

    async def get_order_books(self):
        return await self._post('returnOrderBook')
    get_order_books.__doc__ = Client.get_order_books.__doc__

    async def get_order_book(self, market):
        data = {
            'market': market
        }
        return await self._post('returnOrderBook', False, json=data)
    get_order_book.__doc__ = Client.get_order_book.__doc__

    async def get_open_orders(self, market, address):
        data = {
            'market': market,
            'address': address
        }
        return await self._post('returnOpenOrders', False, json=data)
    get_open_orders.__doc__ = Client.get_open_orders.__doc__

    @require_address
    async def get_my_open_orders(self, market):
        return await self.get_open_orders(market, self._wallet_address)
    get_my_open_orders.__doc__ = Client.get_my_open_orders.__doc__

    async def get_trade_history(self, market=None, address=None, start=None, end=None):
        data = {}
        if market:
            data['market'] = market
        if address:
            data['address'] = address
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        return await self._post('returnTradeHistory', False, json=data)
    get_trade_history.__doc__ = Client.get_trade_history.__doc__

    @require_address
    async def get_my_trade_history(self, market=None, start=None, end=None):
        return await self.get_trade_history(market, self._wallet_address, start, end)
    get_my_trade_history.__doc__ = Client.get_my_trade_history.__doc__

    async def get_currencies(self):
        return await self._post('returnCurrencies')
    get_currencies.__doc__ = Client.get_currencies.__doc__

    async def get_currency(self, currency):
        if currency not in self._currency_addresses:
            self._currency_addresses = await self.get_currencies()

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
    get_currency.__doc__ = Client.get_currency.__doc__

    async def get_balances(self, address, complete=False):
        data = {
            'address': address
        }

        path = 'returnBalances'
        if complete:
            path = 'returnCompleteBalances'

        return await self._post(path, False, json=data)
    get_balances.__doc__ = Client.get_balances.__doc__

    @require_address
    async def get_my_balances(self, complete=False):
        return await self.get_balances(self._wallet_address, complete)
    get_my_balances.__doc__ = Client.get_my_balances.__doc__

    async def get_transfers(self, address, start=None, end=None):

        data = {
            'address': address
        }
        if start:
            data['start'] = start
        if end:
            data['end'] = end

        return await self._post('returnDepositsWithdrawals', False, json=data)
    get_transfers.__doc__ = Client.get_transfers.__doc__

    @require_address
    async def get_my_transfers(self, start=None, end=None):
        return await self.get_transfers(self._wallet_address, start, end)
    get_my_transfers.__doc__ = Client.get_my_transfers.__doc__

    async def get_order_trades(self, order_hash):
        data = {
            'orderHash': order_hash
        }

        return await self._post('returnOrderTrades', False, json=data)
    get_order_trades.__doc__ = Client.get_order_trades.__doc__

    async def get_next_nonce(self, address):
        data = {
            'address': address
        }
        return await self._post('returnNextNonce', False, json=data)
    get_next_nonce.__doc__ = Client.get_next_nonce.__doc__

    @require_address
    async def get_my_next_nonce(self):
        return await self.get_next_nonce(self._wallet_address)
    get_my_next_nonce.__doc__ = Client.get_my_next_nonce.__doc__

    async def _get_contract_address(self):
        if not self._contract_address:
            res = await self.get_contract_address()
            self._contract_address = res['address']

        return self._contract_address
    _get_contract_address.__doc__ = Client._get_contract_address.__doc__

    async def get_contract_address(self):
        return await self._post('returnContractAddress')
    get_contract_address.__doc__ = Client.get_contract_address.__doc__

    # Trade Endpoints

    async def parse_from_currency_quantity(self, currency, quantity):
        currency_details = await self.get_currency(currency)

        return self._parse_from_currency_quantity(currency_details, quantity)
    parse_from_currency_quantity.__doc__ = Client.parse_from_currency_quantity.__doc__

    async def convert_to_currency_quantity(self, currency, quantity):
        currency_details = await self.get_currency(currency)

        return self._convert_to_currency_quantity(currency_details, quantity)
    convert_to_currency_quantity.__doc__ = Client.convert_to_currency_quantity.__doc__

    @require_address
    async def create_order(self, token_buy, token_sell, price, quantity):

        # convert buy and sell amounts based on decimals
        price = self._num_to_decimal(price)
        quantity = self._num_to_decimal(quantity)
        sell_quantity = price * quantity
        amount_buy = await self.convert_to_currency_quantity(token_buy, quantity)
        amount_sell = await self.convert_to_currency_quantity(token_sell, sell_quantity)

        return await self.create_order_wei(token_buy, token_sell, amount_buy, amount_sell)
    create_order.__doc__ = Client.create_order.__doc__

    @require_address
    @require_private_key
    async def create_order_wei(self, token_buy, token_sell, amount_buy, amount_sell):

        contract_address = await self._get_contract_address()

        buy_currency = await self.get_currency(token_buy)
        sell_currency = await self.get_currency(token_sell)

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

        return await self._post('order', True, hash_data=hash_data)
    create_order_wei.__doc__ = Client.create_order_wei.__doc__

    @require_address
    @require_private_key
    async def create_trade(self, order_hash, token, amount):
        amount_trade = await self.convert_to_currency_quantity(token, amount)

        hash_data = [
            ['orderHash', order_hash, 'address'],
            ['amount', amount_trade, 'uint256'],
            ['address', self._wallet_address, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        return await self._post('trade', True, hash_data=hash_data)
    create_trade.__doc__ = Client.create_trade.__doc__

    @require_address
    @require_private_key
    async def cancel_order(self, order_hash):

        hash_data = [
            ['orderHash', order_hash, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        json_data = {
            'address': self._wallet_address
        }

        return await self._post('cancel', True, hash_data=hash_data, json=json_data)
    cancel_order.__doc__ = Client.cancel_order.__doc__

    # Withdraw Endpoints

    @require_address
    @require_private_key
    async def withdraw(self, amount, token):
        contract_address = await self._get_contract_address()

        currency = await self.get_currency(token)

        # convert amount
        amount = await self.convert_to_currency_quantity(token, amount)

        hash_data = [
            ['contractAddress', contract_address, 'address'],
            ['token', currency['address'], 'address'],
            ['amount', amount, 'uint256'],
            ['address', self._wallet_address, 'address'],
            ['nonce', self._get_nonce(), 'uint256'],
        ]

        return await self._post('withdraw', True, hash_data=hash_data)
    withdraw.__doc__ = Client.withdraw.__doc__
