=============================
Welcome to python-idex v3.0.0
=============================

.. image:: https://img.shields.io/pypi/v/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/pypi/l/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/travis/sammchardy/python-idex.svg
    :target: https://app.travis-ci.com/github/sammchardy/python-idex

.. image:: https://img.shields.io/coveralls/sammchardy/python-idex.svg
    :target: https://coveralls.io/github/sammchardy/python-idex

.. image:: https://img.shields.io/pypi/wheel/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/pypi/pyversions/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

This is an unofficial Python wrapper for the `IDEX exchanges REST API v3 <https://api-docs-v3.idex.io/>`_. I am in no way affiliated with IDEX, use at your own risk.

PyPi
  https://pypi.python.org/pypi/python-idex

Source code
  https://github.com/sammchardy/python-idex

Documentation
  https://python-idex.readthedocs.io/en/latest/


Features
--------

- Implementation of all REST endpoints except for deposit.
- Response exception handling
- Liquidity endpoints


Notes
-----

Using an API key increases `rate limits <https://api-docs-v3.idex.io/#rate-limits>`_.

Quick Start
-----------

Register an account with `IDEX v3 <https://exchange.idex.io/r/O5O9RA3B>`_.

.. code:: bash

    pip install python-idex


Synchronous Examples
--------------------

.. code:: python

    # Unauthenticated

    from idex import Client
    client = Client()

    # server time
    time = client.get_server_time()

    # get exchange_info
    exchange_info = client.get_exchange()

    # get assets
    assets = client.get_assets()

    # get markets
    markets = client.get_markets()

    # get market depth
    depth = client.get_order_book(market='ETH-USDC')

    # get liquidity pools
    pools = client.get_liquidity_pools()

    # Authenticated

    api_key = '<api_key>'
    address = '<address_string>'
    private_key = '<wallet_private_key_string>'
    client = Client(api_key, address, private_key)

    # get your balances
    balances = client.get_balances()

    # get your open orders
    orders = client.get_open_orders()

    # create a market order
    order = client.create_market_order(
        market='ETH-USDC',
        order_side=OrderSide.BUY,
        quantity=1000
    )

    # create a limit order
    order = client.create_limit_order(
        market='ETH-USDC',
        order_side=OrderSide.BUY,
        quantity=1000,
        price=2100,
    )


Async Example
-------------

.. code:: python

    from idex import AsyncClient


    async def main():

        # Initialise the client
        client = await AsyncClient.create()

        # get currencies
        currencies = await client.get_currencies()

        # get market depth
        depth = await client.get_order_book('ETH_SENT')

        # get your balances
        balances = await client.get_my_balances()

        # get your open orders
        orders = await client.get_my_open_orders('ETH_SENT')

        # create a limit order
        order = await client.create_order('SENT', 'ETH', '0.001', '10000')

        # Authenticated

        api_key = '<api_key>'
        address = '<address_string>'
        private_key = '<wallet_private_key_string>'
        client = await AsyncClient.create(api_key, address, private_key)

        # get your balances
        balances = await client.get_balances()

        # get your open orders
        orders = await client.get_open_orders()

        # create a market order
        order = await client.create_market_order(
            market='ETH-USDC',
            order_side=OrderSide.BUY,
            quantity=1000
        )

        # create a limit order
        order = await client.create_limit_order(
            market='ETH-USDC',
            order_side=OrderSide.BUY,
            quantity=1000,
            price=2100,
        )

    if __name__ == "__main__":
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())

Wallet
------

The examples above use the wallet private key when creating the Client to specify
which wallet to interact with.

Most functions will have a `wallet_address` parameter to target a different wallet.

If a new wallet is needed for subsequent calls `init_wallet` can be used to change the
internal wallet

... code:python

    private_key = '<old_private_key>'
    client = Client(api_key, address, private_key)
    client.init_wallet(private_key='<new_wallet_private_key>')

    # this will fetch balance of the new wallet
    client.get_balance()

Sandbox
-------

IDEX v3 supports a sandbox to test functionality.

Enable it by passing `sandbox=True` when creating the client

... code:python

    client = Client(sandbox=True)

    # or async

    client = await AsyncClient.create(sandbox=True)

Test Orders
-----------

All order functions allow for test orders to be sent, just set `test=True` when calling a test function



Donate
------

If this library helped you out feel free to donate.

- ETH: 0xD7a7fDdCfA687073d7cC93E9E51829a727f9fE70
- IDEX: 0xD7a7fDdCfA687073d7cC93E9E51829a727f9fE70 (Polygon)
- NEO: AVJB4ZgN7VgSUtArCt94y7ZYT6d5NDfpBo
- LTC: LPC5vw9ajR1YndE1hYVeo3kJ9LdHjcRCUZ
- BTC: 1Dknp6L6oRZrHDECRedihPzx2sSfmvEBys

Other Exchanges
---------------

If you use `Binance <https://www.binance.com/?ref=10099792>`_ check out my `python-binance <https://github.com/sammchardy/python-binance>`_ library.

If you use `Binance Chain <https://testnet.binance.org/>`_ check out my `python-binance-chain <https://github.com/sammchardy/python-binance-chain>`_ library.

If you use `Kucoin <https://www.kucoin.com/?rcode=E42cWB>`_ check out my `python-kucoin <https://github.com/sammchardy/python-kucoin>`_ library.

.. image:: https://analytics-pixel.appspot.com/UA-111417213-1/github/python-idex?pixel
