import asyncio
import json
import logging
import websockets as ws


class ReconnectingWebsocket:

    STREAM_URL = 'wss://api-cluster.idex.market'
    MAX_RECONNECTS = 3
    MIN_RECONNECT_WAIT = 0.1
    TIMEOUT = 10

    def __init__(self, loop, coro):
        self._loop = loop
        self._log = logging.getLogger(__name__)
        self._coro = coro
        self._reconnects = 0
        self._reconnect_wait = 0.1
        self._conn = None
        self._socket = None

        self._connect()

    def _connect(self):
        self._conn = asyncio.ensure_future(self._run())

    async def _run(self):

        keep_waiting = True

        async with ws.connect(self.STREAM_URL) as socket:
            self._socket = socket
            try:
                self._reconnect_wait = self.MIN_RECONNECT_WAIT
                while keep_waiting:
                    try:
                        evt = await asyncio.wait_for(self._socket.recv(), timeout=self.TIMEOUT)
                    except asyncio.TimeoutError:
                        print("no message in {} seconds".format(self.TIMEOUT))
                        await self._socket.ping()
                    except asyncio.CancelledError:
                        print("cancelled error")
                        await self._socket.ping()
                    else:
                        try:
                            evt_obj = json.loads(evt)
                        except ValueError:
                            pass
                        else:
                            await self._coro(evt_obj)

            except ws.ConnectionClosed as e:
                keep_waiting = False
                await self._reconnect()
            except Exception as e:
                self._log.debug('ws exception:{}'.format(e))
                keep_waiting = False
            #    await self._reconnect()

    async def _reconnect(self):
        await self.cancel()
        self._reconnects += 1
        if self._reconnects < self.MAX_RECONNECTS:

            self._log.debug("websocket {} reconnecting {} reconnects left".format(self._path, self.MAX_RECONNECTS - self._reconnects))
            await asyncio.sleep(self._reconnect_wait)
            self._reconnect_wait *= 3
            self._connect()
        else:
            # maybe raise an exception
            pass

    async def send_message(self, msg):
        wait_count = 0
        if not self._socket:
            print("waiting for socket to init")
            wait_count += 1
            if wait_count < 3:
                await asyncio.sleep(1)
        await self._socket.send(msg)

    async def cancel(self):
        self._conn.cancel()


class IdexSocketManager:

    def __init__(self):
        """Initialise the IdexSocketManager

        """
        self._coros = {}
        self._conn = None
        self._loop = None

    @classmethod
    async def create(cls, loop):
        self = IdexSocketManager()
        self._loop = loop
        self._conn = ReconnectingWebsocket(loop, self._recv)
        print(self._conn)
        return self

    async def _recv(self, msg):
        # get topic
        if 'topic' in msg:
            topic = msg['topic']
            await self._coros[topic](msg['message'], topic)

    async def subscribe(self, market, coro):
        """Subscribe to a market

        https://github.com/AuroraDAO/idex-api-docs#websocket-api

        :param market: required
        :type market: str
        :param coro: callback coroutine to handle messages for this market
        :type coro: async coroutine

        :returns: None

        Message Formats

        .. code-block:: python

            {
                topic: 'ETH_DVIP',
                message: {
                type: 'orderBookAdd',
                    data: {
                        orderNumber: 2067,
                        orderHash: '0xd9a438e69fbefaf63c327fb8a4dcafd9b1f0faaba428e16013a15328f08c02b2',
                        price: '10',
                        amount: '1',
                        total: '10',
                        type: 'sell',
                        params: {
                            tokenBuy: '0x0000000000000000000000000000000000000000',
                            buyPrecision: 18,
                            amountBuy: '10000000000000000000',
                            tokenSell: '0xadc46ff5434910bd17b24ffb429e585223287d7f',
                            sellPrecision: 2,
                            amountSell: '100',
                            expires: 190000,
                            nonce: 2831,
                            user: '0x034767f3c519f361c5ecf46ebfc08981c629d381'
                        }
                    }
                }
            }

            {
                topic: 'ETH_DVIP',
                message: {
                    type: 'orderBookRemove',
                    data: {
                        orderHash: '0xd9a438e69fbefaf63c327fb8a4dcafd9b1f0faaba428e16013a15328f08c02b2'
                    }
                }
            }

            {
                topic: 'ETH_DVIP',
                message: {
                    type: 'orderBookModify',
                    data: {
                        orderNumber: 2066,
                        orderHash: '0x5b112c1c7089312cd92f5a701b7a4490ae2bde7054f6fd8e5790934cefd49dd1',
                        price: '9',
                        amount: '0.5',
                        total: '4.5',
                        type: 'sell',
                        params: {
                            tokenBuy: '0x0000000000000000000000000000000000000000',
                            buyPrecision: 18,
                            amountBuy: '9000000000000000000',
                            amountBuyRemaining: '4500000000000000000',
                            tokenSell: '0xadc46ff5434910bd17b24ffb429e585223287d7f',
                            sellPrecision: 2,
                            amountSell: '100',
                            amountSellRemaining: '50',
                            expires: 190000,
                            nonce: 2829,
                            user: '0x034767f3c519f361c5ecf46ebfc08981c629d381'
                        }
                    }
                }
            }

            {
                topic: 'ETH_DVIP',
                message: {
                    type: 'newTrade',
                    data: {
                        date: '2017-10-12 23:36:32',
                        amount: '4.5',
                        type: 'buy',
                        total: '0.5',
                        price: '9',
                        orderHash: '0x5b112c1c7089312cd92f5a701b7a4490ae2bde7054f6fd8e5790934cefd49dd1',
                        uuid: '2de5db40-afa6-11e7-9b58-b5b6bfc20bff'
                    }
                }
            }

        """
        if market not in self._coros:
            self._coros[market] = coro
            print(self._conn)
            await self._conn.send_message(json.dumps({"subscribe": market}))

    async def unsubscribe(self, market):
        """Unsubscribe from a market

        https://github.com/AuroraDAO/idex-api-docs#websocket-api

        :param market: required
        :type market: str

        :returns: None

        """
        if market in self._coros:
            del self._coros[market]
            await self._conn.send_message(json.dumps({"unsubscribe": market}))
