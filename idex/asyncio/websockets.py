import asyncio
import json
import logging
from random import random
from typing import List, Union, Dict, Callable, Awaitable
from enum import Enum

from shortid import ShortId
import websockets as ws


class SubscribeCategory(str, Enum):
    account = 'subscribeToAccounts'
    accounts = 'subscribeToAccounts'
    market = 'subscribeToMarkets'
    markets = 'subscribeToMarkets'
    chain = 'subscribeToChains'
    chains = 'subscribeToChains'


class ReconnectingWebsocket:

    STREAM_URL: str = 'wss://datastream.idex.market'
    MAX_RECONNECTS: int = 5
    MAX_RECONNECT_SECONDS: int = 60
    MIN_RECONNECT_WAIT = 0.1
    TIMEOUT: int = 10
    PROTOCOL_VERSION: str = '1.0.0'

    def __init__(self, loop, coro, api_key):
        self._loop = loop
        self._log = logging.getLogger(__name__)
        self._coro = coro
        self._reconnect_attempts: int = 0
        self._conn = None
        self._socket: ws.client.WebSocketClientProtocol = None
        self._sid: str = None
        self._handshaken: bool = False
        self._api_key = api_key

        self._connect()

    def set_sid(self, sid: str):
        self._sid = sid

    def _connect(self):
        self._conn = asyncio.ensure_future(self._run())

    async def _run(self):

        keep_waiting: bool = True

        async with ws.connect(self.STREAM_URL, ssl=True) as socket:
            self._socket = socket

            await self.handshake()
            try:
                while keep_waiting:
                    try:
                        evt = await asyncio.wait_for(self._socket.recv(), timeout=self.TIMEOUT)
                    except asyncio.TimeoutError:
                        self._log.debug("no message in {} seconds".format(self.TIMEOUT))
                        await self._socket.ping()
                    except asyncio.CancelledError:
                        self._log.debug("cancelled error")
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
        self._reconnect_attempts += 1
        if self._reconnect_attempts < self.MAX_RECONNECTS:

            self._log.debug(f"websocket reconnecting {self.MAX_RECONNECTS - self._reconnect_attempts} attempts left")
            reconnect_wait = self._get_reconnect_wait(self._reconnect_attempts)
            await asyncio.sleep(reconnect_wait)
            self._handshaken = False
            self._connect()
        else:
            # maybe raise an exception
            self._log.error(f"websocket could not reconnect after {self._reconnect_attempts} attempts")
            pass

    def _get_reconnect_wait(self, attempts: int) -> int:
        expo = 2 ** attempts
        return round(random() * min(self.MAX_RECONNECT_SECONDS, expo - 1) * 1000 + 1)

    async def send_message(self, category: SubscribeCategory, msg):
        wait_count = 0
        if not self._socket or not self._sid:
            self._log.debug("waiting for socket to init and handshake")
            wait_count += 1
            if wait_count < 5:
                await asyncio.sleep(1)

        # build the message
        rid = ShortId()
        socket_msg = json.dumps({
            "rid": f"rid:{rid.generate()}",
            "sid": self._sid,
            "request": category,
            "payload": json.dumps(msg)
        })
        await self._socket.send(socket_msg)

    async def handshake(self):
        if self._handshaken:
            return

        self._handshaken = True

        handshake = json.dumps({
            'request': 'handshake',
            'payload': json.dumps({
                # 'locale': 'en-au',
                # 'type': 'client',
                'version': self.PROTOCOL_VERSION,
                'key': self._api_key
            })
        })
        await self._socket.send(handshake)

    async def cancel(self):
        self._conn.cancel()


class IdexSocketManager:

    def __init__(self):
        """Initialise the IdexSocketManager

        """
        self._callback: Callable[[int], Awaitable[str]]
        self._conn = None
        self._loop = None
        self._log = logging.getLogger(__name__)

    @classmethod
    async def create(cls, loop, callback: Callable[[int], Awaitable[str]], api_key):
        self = IdexSocketManager()
        self._loop = loop
        self._callback = callback
        self._conn = ReconnectingWebsocket(loop, self._recv, api_key=api_key)
        return self

    async def _recv(self, msg: Dict):
        # self._log.debug(f"mes recvd:{msg}")
        # get topic
        if 'result' in msg:
            if msg['result'] == 'success':
                self._conn.set_sid(msg['sid'])

        elif 'event' in msg:

            await self._callback(msg)

    async def subscribe(self, category: SubscribeCategory, topic: Union[str, List[str]], events: [List[str]]):
        """Subscribe to a market or markets

        https://github.com/AuroraDAO/datastream-client-js/blob/master/docs/index.md

        :param category: required
        :param topic: required
        :param events: required
        :returns: None

        Message Formats

        Sample response

        .. code-block:: python

            {
                'chain': 'eth',
                'event': 'market_cancels',
                'payload': '{               # a JSON encoded string
                    "market":"ETH_IDXM",
                    "cancels": [
                        {
                            "id":461889486,
                            "market":
                            "ETH_IDXM",
                            "orderHash":"0xb0ddfd9e919493aaec790da1c089c846396fca5ac4592a340cbd032f65d1bde6",
                            "createdAt":"2019-02-11T09:27:57.000Z"
                        }
                    ]
                }',
                'sid': 'csi:76XcGEza40XPB',
                'eid': 'evt:GTaYL4sEcp5fY',
                'seq': 98
            }


        """

        req_msg = {
            'action': 'subscribe',
            'topics': topic,
            'events': events
        }

        await self._conn.send_message(category, req_msg)

    async def unsubscribe(self, category: SubscribeCategory, topic: Union[str, List[str]], events: [List[str]]):
        """Unsubscribe from a market

        https://github.com/AuroraDAO/datastream-client-js/blob/master/docs/index.md

        :param category: required
        :param topic: required
        :param events: required

        :returns: None

        """

        req_msg = {
            'action': 'unsubscribe',
            'topics': topic,
            'events': events
        }

        await self._conn.send_message(category, req_msg)
