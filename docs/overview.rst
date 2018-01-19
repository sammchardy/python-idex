Getting Started
===============

Installation
------------

``python-idex`` is available on `PYPI <https://pypi.python.org/pypi/python-idex/>`_.
Install with ``pip``:

.. code:: bash

    pip install python-idex


Register on IDEX
----------------

Firstly register an account with `IDEX <https://idex.market/>`_.

Make sure you save your private key as you will need it to sign trades.

Wallet Address
--------------

Your Wallet Address can be found in the top right under the account menu.

This is used to query the exchange for your balances, orders and trade history etc.

Some calls will throw an IdexException unless the wallet address and private key have been set.

Initialise the client
---------------------

Pass your Wallet Address and Private Key

.. code:: python

    from idex.client import Client
    client = Client()

    # add your wallet address later
    client.set_wallet_address(address)

    # change or add wallet address and private key
    client.set_wallet_address(address, private_key)

    # initialise the client with wallet address and private key
    client = Client(address, private_ke)

API Rate Limit
--------------

Unknown
