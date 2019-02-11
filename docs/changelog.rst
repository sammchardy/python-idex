Changelog
=========

v0.3.5 - 2019-02-11
^^^^^^^^^^^^^^^^^^^

**Updated**

- websockets to use new datastream

v0.3.4 - 2019-01-15
^^^^^^^^^^^^^^^^^^^

**Added**

- new endpoint `get_order_status`
- new params for `get_order_book`, `get_open_orders`, `get_my_open_orders`, `get_trade_history`


**Fixed**

- bug in _convert_to_currency_quantity for large values


v0.3.3 - 2018-08-08
^^^^^^^^^^^^^^^^^^^

**Added**

- override params for requests and aiohttp libraries


v0.3.2 - 2018-06-27
^^^^^^^^^^^^^^^^^^^

**Fixed**

- rlp version requirement

v0.3.1 - 2018-06-27
^^^^^^^^^^^^^^^^^^^

**Fixed**

- setup.py requirements

v0.3.0 - 2018-06-21
^^^^^^^^^^^^^^^^^^^

**Added**

- async versions of REST API
- async websocket interface

**Fixed**

- extracted dependencies from pyethereum to utils to fix Windows installs

**Removed**

- Python 3.3 and 3.4 support

v0.2.7 - 2018-01-30
^^^^^^^^^^^^^^^^^^^

**Fixed**

- revert `get_currency` call

v0.2.6 - 2018-01-29
^^^^^^^^^^^^^^^^^^^

**Fixed**

- `get_currency` call with address for token


v0.2.5 - 2018-01-29
^^^^^^^^^^^^^^^^^^^

**Fixed**

- cancel order signature...again

**Added**

- token name parameter to `get_balances` call

v0.2.4 - 2018-01-23
^^^^^^^^^^^^^^^^^^^

**Fixed**

- set wallet address lowercase

**Added**

- validation of private key format

v0.2.3 - 2018-01-20
^^^^^^^^^^^^^^^^^^^

**Fixed**

- order of hash params in `create_trade` function

v0.2.2 - 2018-01-20
^^^^^^^^^^^^^^^^^^^

**Fixed**

- issue with hashed data in `cancel_order` function

v0.2.1 - 2018-01-19
^^^^^^^^^^^^^^^^^^^

**Added**

- Withdraw endpoint

**Fixed**

- issue with Nonce value being too high

v0.2.0 - 2017-11-16
^^^^^^^^^^^^^^^^^^^

**Added**

- Trading endpoints
- Better exception handling
- Reference currency by address as well as name

v0.1.0 - 2017-11-15
^^^^^^^^^^^^^^^^^^^

**Added**

- Implementation of all non trading REST endpoints.
- Helper functions for your wallet address
- Response exception handling
