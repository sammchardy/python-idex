import time
import json
from operator import itemgetter
from typing import Callable, Awaitable, Optional
from decimal import Decimal

from idex.asyncio.client import AsyncClient
from idex.asyncio.websockets import IdexSocketManager, SubscribeCategory


AsyncCoro = Callable[[int], Awaitable[str]]


class DepthCache:

    def __init__(self, symbol):
        """Initialise the DepthCache

        :param symbol: Symbol to create depth cache for
        :type symbol: string

        """
        self.symbol = symbol
        self._bids = {}
        self._asks = {}
        self._orders = {}
        self.update_time = None

    def add_bid(self, order_hash: str, amount: str, price: str):
        """Add a bid to the cache

        :param order_hash:
        :param amount:
        :param price:
        :return:

        """
        if order_hash in self._orders:
            return
        self._orders[order_hash] = (price, amount)
        if price not in self._bids:
            self._bids[price] = Decimal(0)
        self._bids[price] += Decimal(amount)

    def add_ask(self, order_hash: str, amount: str, price: str):
        """Add an ask to the cache

        :param order_hash:
        :param amount:
        :param price:
        :return:

        """
        if order_hash in self._orders:
            return
        self._orders[order_hash] = (price, amount)
        if price not in self._asks:
            self._asks[price] = Decimal(0)
        self._asks[price] += Decimal(amount)

    def cancel_order(self, order_hash: str):
        """Remove an order from the books

        :param order_hash:
        :return:

        """
        if order_hash not in self._orders:
            return
        price, amount = self._orders[order_hash]
        if price in self._bids:
            self._bids[price] -= Decimal(amount)
            # clear 0 amounts
            if self._bids[price] == Decimal(0):
                del self._bids[price]
        elif price in self._asks:
            self._asks[price] -= Decimal(amount)
            # clear 0 amounts
            if self._asks[price] == Decimal(0):
                del self._asks[price]
        del self._orders[order_hash]

    def get_bids(self):
        """Get the current bids

        :return: list of bids with price and quantity as floats

        .. code-block:: python

            [
                [
                    0.0001946,  # Price
                    45.0        # Quantity
                ],
                [
                    0.00019459,
                    2384.0
                ],
                [
                    0.00019158,
                    5219.0
                ],
                [
                    0.00019157,
                    1180.0
                ],
                [
                    0.00019082,
                    287.0
                ]
            ]

        """
        return DepthCache.sort_depth(self._bids, reverse=True)

    def get_asks(self):
        """Get the current asks

        :return: list of asks with price and quantity as floats

        .. code-block:: python

            [
                [
                    0.0001955,  # Price
                    57.0'       # Quantity
                ],
                [
                    0.00019699,
                    778.0
                ],
                [
                    0.000197,
                    64.0
                ],
                [
                    0.00019709,
                    1130.0
                ],
                [
                    0.0001971,
                    385.0
                ]
            ]

        """
        return DepthCache.sort_depth(self._asks, reverse=False)

    @staticmethod
    def sort_depth(vals, reverse=False):
        """Sort bids or asks by price
        """
        lst = [[float(price), float(quantity)] for price, quantity in vals.items()]
        lst = sorted(lst, key=itemgetter(0), reverse=reverse)
        return lst


class DepthCacheManager(object):

    _default_refresh = 60 * 30  # 30 minutes

    @classmethod
    async def create(
        cls,
        client: AsyncClient,
        loop,
        symbol: str,
        coro: Optional[AsyncCoro] = None,
        refresh_interval: int = _default_refresh
    ):
        """Create a DepthCacheManager instance

        :param client: IDEX Async API client
        :param loop:
        :param symbol: Symbol to create depth cache for
        :param coro: Optional coroutine to receive depth cache updates
        :param refresh_interval: Optional number of seconds between cache refresh, use 0 or None to disable

        """

        self = DepthCacheManager()
        self._client = client
        self._loop = loop
        self._symbol = symbol
        self._coro = coro
        self._ism = None
        self._depth_cache = DepthCache(self._symbol)
        self._refresh_interval = refresh_interval

        self._base_token, self._quote_token = self._symbol.split('_')
        self._base_currency = await self._client.get_currency(self._base_token)
        self._quote_currency = await self._client.get_currency(self._quote_token)

        await self._start_socket()
        await self._init_cache()

        return self

    async def _init_cache(self):
        """Initialise the depth cache calling REST endpoint

        :return:
        """

        self._depth_cache = DepthCache(self._symbol)
        res = await self._client.get_order_book(market=self._symbol, count=100)

        # process bid and asks from the order book
        for bid in res['bids']:
            self._depth_cache.add_bid(bid['orderHash'], bid['amount'], bid['price'])
        for ask in res['asks']:
            self._depth_cache.add_ask(ask['orderHash'], ask['amount'], ask['price'])

        # set a time to refresh the depth cache
        if self._refresh_interval:
            self._refresh_time = int(time.time()) + self._refresh_interval

    async def _start_socket(self):
        """Start the depth cache socket

        :return:
        """
        self._ism = await IdexSocketManager.create(self._loop, self._depth_event)

        await self._ism.subscribe(
            SubscribeCategory.markets,
            [self._symbol],
            ["market_trades", "market_orders", "market_cancels", ]
        )

    async def _depth_event(self, msg):
        """Handle a depth event

        :param msg:
        :return:

        """

        if 'event' not in msg:
            return

        payload = json.loads(msg['payload'])

        # if order message
        if msg['event'] == 'market_orders':

            for order in payload['orders']:
                order_hash = order['hash']
                buy = payload['orders'][0]['amountBuy']
                sell = payload['orders'][0]['amountSell']
                # work out if it's a bid or an ask
                if order['tokenBuy'] == self._base_currency['address']:  # ETH_LTO
                    # ask
                    sell_parsed = await self._client.parse_from_currency_quantity(self._quote_token, sell)
                    buy_parsed = await self._client.parse_from_currency_quantity(self._base_token, buy)
                    amount = f'{sell_parsed:.18}'
                    price = f'{(buy_parsed / sell_parsed):.18}'
                    self._depth_cache.add_ask(order_hash, amount, price)
                else:
                    # bid
                    sell_parsed = await self._client.parse_from_currency_quantity(self._base_token, sell)
                    buy_parsed = await self._client.parse_from_currency_quantity(self._quote_token, buy)
                    amount = f'{buy_parsed:.18}'
                    price = f'{(sell_parsed / buy_parsed):.18}'
                    self._depth_cache.add_bid(order_hash, amount, price)

        # if cancel message
        elif msg['event'] == 'market_cancels':

            for order in payload['cancels']:
                order_hash = order['orderHash']
                # remove the order

                self._depth_cache.cancel_order(order_hash)

        # if trade
        elif msg['event'] == 'market_trades':
            # work out what to do...
            """
            {'chain': 'eth', 'event': 'market_trades', 'payload': '{"market":"ETH_LTO","total":9,"highestTimestamp":1550059823,"trades":[{"tid":3212983,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"1194.978508789538123658","price":"0.00086718507708843","amount":"11365.16763878","total":"9.855703774967036111","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x0a1f4f0845af497842956a48440960d27dcbf2c9","orderHash":"0x0aef9904bdad09d47788461a6ea4ac33287ed1a5f44f938dd3d5a6acf221ea16","gasFee":"2.352439005116982127","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"22.73033527756","sellerFee":"0.009855703774967036","amountWei":"9855703774967036111","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212984,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"315.426337010770091133","price":"0.00086717","amount":"3000","total":"2.60151","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0xa4ff7ff49d447c01e37aafa89b27c15bc76652d3","orderHash":"0xca238506b993dc848b3a830c027a0aa3a5ef426b1af7e8c9352800ce7b719349","gasFee":"2.352479905900803","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"6","sellerFee":"0.00260151","amountWei":"2601510000000000000","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212985,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"75.303873147669703119","price":"0.000867169999999999","amount":"716.21038872","total":"0.621076162786321684","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x2ae9754696519f6e19b0449c4950b0030110c567","orderHash":"0xd8300cd2ed9e030a4a336f0ff9e850bb0775c2c78c0823f5441d22726876ad31","gasFee":"2.352479905900806393","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"1.43242077744","sellerFee":"0.000621076162786322","amountWei":"621076162786321684","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212986,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"959.638051722036966298","price":"0.00086618507708843","amount":"9137.4352","total":"7.914710013102533794","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x0a1f4f0845af497842956a48440960d27dcbf2c9","orderHash":"0xa9ce4319c3ea736667ae0aef19fc7fb16df599fe419904c8db36fe6e79b5c6b1","gasFee":"2.355154866968145049","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"18.2748704","sellerFee":"0.007914710013102534","amountWei":"7914710013102533794","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212987,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"1856.431117433307902679","price":"0.000857161328299999","amount":"17862.5648","total":"15.311099770812805977","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x0a1f4f0845af497842956a48440960d27dcbf2c9","orderHash":"0xcca785769875639f65f31eef31a62fe5ddc0f11c60f4f685d87d291f0494cbfa","gasFee":"2.379948712858878338","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"35.7251296","sellerFee":"0.015311099770812806","amountWei":"15311099770812805977","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212988,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"19.611635625765313415","price":"0.00085700558827222","amount":"188.73728738","total":"0.16174891","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x79147f4a41d558d2340034f7ef41525edd2966d0","orderHash":"0x505b15c51f31860cd6dbd9b69491b87872cebfa851456d53b808c7be15ab3d49","gasFee":"2.380381210947263704","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"0.37747457476","sellerFee":"0.00016174891","amountWei":"161748910000000000","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212989,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"1212.474051648930730309","price":"0.000851919891569812","amount":"11738.19287347","total":"9.999999999992102349","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x00a81b97bce4df53df5e279d1feba8d729c966ef","orderHash":"0xc1d0f17fe9211cbcdfe49bd1315b9a41a9f62cc379170b73335512c8df722b7d","gasFee":"2.394591346189769849","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"23.47638574694","sellerFee":"0.009999999999992102","amountWei":"9999999999992102349","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212990,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"127.129484689242031406","price":"0.000851766559023008","amount":"1230.9863814","total":"1.04851303428926246","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0xc7ef927b791bc8c7d6e25625a06e34016943e3d2","orderHash":"0xdedfeb01a9084afa78f0c0fa6496648afd775f992ecad754a5ecfc1b689133ab","gasFee":"2.39502241358232813","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"2.4619727628","sellerFee":"0.001048513034289262","amountWei":"1048513034289262460","updatedAt":"2019-02-13T12:10:23.000Z"},{"tid":3212991,"type":"buy","date":"2019-02-13T12:10:23.000Z","timestamp":1550059823,"market":"ETH_LTO","usdValue":"179.944380999336438451","price":"0.000851758041357418","amount":"1742.4069489","total":"1.48410913004261831","taker":"0xe4357ff0845b07d74f0bf8f6a6825b2381762b22","maker":"0x55ec6b5d7b64466c008b37f8117495fd54076f21","orderHash":"0x2c1d784c4059783213a04b42d6c698ec146ce08fc1aac8fdfeba65b98f10d6b0","gasFee":"2.395046364045967926","tokenBuy":"0x0000000000000000000000000000000000000000","tokenSell":"0x3db6ba6ab6f95efed1a6e794cad492faaabf294d","buyerFee":"3.4848138978","sellerFee":"0.001484109130042618","amountWei":"1484109130042618310","updatedAt":"2019-02-13T12:10:23.000Z"}]}', 'sid': 'csi:aTxIO4noYmJIv', 'eid': 'evt:1tKLmDJQX2RMn', 'seq': 2}
            """
            pass

        # call the callback with the updated depth cache
        if self._coro:
            await self._coro(self._depth_cache)

        # after processing event see if we need to refresh the depth cache
        if self._refresh_interval and int(time.time()) > self._refresh_time:
            await self._init_cache()

    def get_depth_cache(self):
        """Get the current depth cache

        :return: DepthCache object

        """
        return self._depth_cache

    async def close(self):
        """Close the open socket for this manager

        :return:
        """
        await self._ism.close()
        self._depth_cache = None
