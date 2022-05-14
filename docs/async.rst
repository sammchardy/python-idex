Async
=====

In v0.3.0 async functionality was added for all REST API methods. This is only supported on Python 3.5+


Example
-------

.. code::python

    from idex import AsyncClient

    api_key = '<api_key>'
    api_secret = '<api_secret>'
    private_key = '0x...'

    async def main():

        # initialise the client
        client = await AsyncClient.create(api_key, api_secret, private_key)

        exchange_info = await client.get_exchange()

        open_orders = await client.get_open_orders('ETH-USDC'))

        print(json.dumps(await client.get_order_books(), indent=2))


    if __name__ == "__main__":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())