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


Private Key
-----------

To perform and trading you will need both your wallet address and private key.

Note: Your private key is in the form '0x4efd9306gf134f9ee432d7415fb385029db50e7bce1682b2442beba24cf0a91f'

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
    client = Client(address, private_key)

API Rate Limit
--------------

Unknown

Requests Settings
-----------------

`python-idex` uses the `requests <http://docs.python-requests.org/>`_ library and the
`aiohttp <https://aiohttp.readthedocs.io/>`_ library.

You can set custom requests parameters for all API calls when creating the client.

.. code:: python

    # for non-asyncio
    client = Client("api-key", "api-secret", {"verify": False, "timeout": 20})

    # for asyncio
    client = Client("api-key", "api-secret", {"verify_ssl": False, "timeout": 20})

You may also pass custom requests parameters through any API call to override default settings or the above settingsspecify new ones like the example below.

.. code:: python

    # this would result in verify: False and timeout: 5 for the get_all_orders call
    client = Client("api-key", "api-secret", {"verify": False, "timeout": 20})
    client.get_all_orders(symbol='BNBBTC', requests_params={'timeout': 5})

Check out the `requests documentation <http://docs.python-requests.org/en/master/>`_ for all options.

**Proxy Settings**

You can use the Requests Settings method above

.. code:: python

    proxies = {
        'http': 'http://10.10.1.10:3128',
        'https': 'http://10.10.1.10:1080'
    }

    # in the Client instantiation
    client = Client("api-key", "api-secret", {'proxies': proxies})

    # or on an individual call
    client.get_all_orders(symbol='BNBBTC', requests_params={'proxies': proxies})

Or set an environment variable for your proxy if required to work across all requests.

An example for Linux environments from the `requests Proxies documentation <http://docs.python-requests.org/en/master/user/advanced/#proxies>`_ is as follows.

.. code-block:: bash

    $ export HTTP_PROXY="http://10.10.1.10:3128"
    $ export HTTPS_PROXY="http://10.10.1.10:1080"

For Windows environments

.. code-block:: bash

    C:\>set HTTP_PROXY=http://10.10.1.10:3128
    C:\>set HTTPS_PROXY=http://10.10.1.10:1080
