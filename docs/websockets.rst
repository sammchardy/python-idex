Websockets
==========

Websockets are only available for Python 3.5+.

The IDEX `Websocket documentation <https://github.com/AuroraDAO/idex-api-docs#websocket-api>`_ describes the
type of messages that can be returned from the websocket.

These include
 - orders added to the order book
 - orders removed from the order book
 - orders modified in the order book
 - new trades

So far only new trade events are received.

Example
-------

.. code::python

    from idex.asyncio import IdexSocketManager

    loop = None

    async def main():
        global loop

        # Initialise the socket manager
        ism = await IdexSocketManager.create(loop)

        # Coroutine to receive messages
        async def handle_evt(msg, topic):
            print("topic:{} type:{}".format(topic, msg['type']))

        # Subscribe to updates for the ETH_NPXS market
        await ism.subscribe('ETH_NPXS', handle_evt)

        # keep the script running so we can retrieve events
        while True:
            await asyncio.sleep(20, loop=loop)


    if __name__ == "__main__":
        # get a loop and switch from synchronous to async
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
