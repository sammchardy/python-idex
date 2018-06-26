Async
=====

In v0.3.0 async functionality was added for all REST API methods. This is only supported on Python 3.5+


Example
-------

.. code::python

    from idex.asyncio import AsyncClient

    address = '0x...'
    private_key = '0x...'
    loop = None

    async def main():
        global loop

        # initialise the client
        client = await AsyncClient.create(address, private_key)


        volume = await client.get_24hr_volume()

        orders = await client.get_open_orders('ETH_NPXS', address))

        print(json.dumps(await client.get_order_books(), indent=2))


    if __name__ == "__main__":
        # get a loop and switch from synchronous to async
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())