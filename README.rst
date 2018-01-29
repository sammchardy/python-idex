=============================
Welcome to python-idex v0.2.6
=============================

.. image:: https://img.shields.io/pypi/v/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/pypi/l/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/travis/sammchardy/python-idex.svg
    :target: https://travis-ci.org/sammchardy/python-idex

.. image:: https://img.shields.io/coveralls/sammchardy/python-idex.svg
    :target: https://coveralls.io/github/sammchardy/python-idex

.. image:: https://img.shields.io/pypi/wheel/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

.. image:: https://img.shields.io/pypi/pyversions/python-idex.svg
    :target: https://pypi.python.org/pypi/python-idex

This is an unofficial Python wrapper for the `IDEX exchanges REST API v1 <https://github.com/AuroraDAO/idex-api-docs>`_. I am in no way affiliated with IDEX, use at your own risk.

PyPi
  https://pypi.python.org/pypi/python-idex

Source code
  https://github.com/sammchardy/python-idex

Documentation
  https://python-idex.readthedocs.io/en/latest/


Features
--------

- Implementation of all REST endpoints except for withdraw/deposit.
- Helper functions for your wallet address
- Response exception handling

Quick Start
-----------

Register an account with `IDEX <https://idex.market/>`_.

.. code:: bash

    pip install python-idex


.. code:: python

    from idex.client import Client
    client = Client(address, private_key)

    # get currencies
    currencies = client.get_currencies()

    # get market depth
    depth = client.get_order_book('ETH_SAN')

    # get your balances
    balances = client.get_my_balances()

    # get your open orders
    orders = client.get_my_open_orders('ETH_SAN')

    # create a limit order
    order = client.create_order('SAN', 'ETH', '0.001', '10000')


For more `check out the documentation <https://github.com/AuroraDAO/idex-api-docs>`_.

TODO
----

- Withdraw/deposit endpoints
- Websocket endpoints

Donate
------

If this library helped you out feel free to donate.

- ETH: 0xD7a7fDdCfA687073d7cC93E9E51829a727f9fE70
- NEO: AVJB4ZgN7VgSUtArCt94y7ZYT6d5NDfpBo
- LTC: LPC5vw9ajR1YndE1hYVeo3kJ9LdHjcRCUZ
- BTC: 1Dknp6L6oRZrHDECRedihPzx2sSfmvEBys

Other Exchanges
---------------

If you use `Binance <https://www.binance.com/?ref=10099792>`_ check out my `python-binance <https://github.com/sammchardy/python-binance>`_ library.

If you use `Quoinex <https://quoinex.com/>`_
or `Qryptos <https://qryptos.com/>`_ check out my `python-quoine <https://github.com/sammchardy/python-quoine>`_ library.

If you use `Exx <https://www.exx.com/r/e8d10713544a2da74f91178feae775f9>`_ check out my `python-exx <https://github.com/sammchardy/python-exx>`_ library.

If you use `Kucoin <https://www.kucoin.com/#/?r=E42cWB>`_ check out my `python-kucoin <https://github.com/sammchardy/python-kucoin>`_ library.

If you use `BigONE <https://big.one>`_ check out my `python-bigone <https://github.com/sammchardy/python-bigone>`_ library.

.. image:: https://analytics-pixel.appspot.com/UA-111417213-1/github/python-idex?pixel