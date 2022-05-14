Getting Started
===============

Installation
------------

``python-idex`` is available on `PYPI <https://pypi.python.org/pypi/python-idex/>`_.
Install with ``pip``:

.. code:: bash

    pip install python-idex


Register on IDEX v3
-------------------

Firstly register an account with `IDEX v3 <https://exchange.idex.io/r/O5O9RA3B>`_.

Make sure you save your private key as you will need it to sign trades.

API Credentials
---------------

Generate an API key and secret using the `Manage User <https://exchange.idex.io/user/manage>`_.

Specify the permissions you require and remember to save both the key and the secret.


Private Key
-----------

To perform and trading you will need both your api credentials and private key.

Note: Your private key is in the form '0x4efd9306gf134f9ee432d7415fb385029db50e7bce1682b2442beba24cf0a91f'

Initialise the client
---------------------

Pass your Private Key

.. code:: python

    from idex import Client
    client = Client(api_key, api_secret)

    # add your wallet private key later
    client.set_wallet(private_key)

    # initialise the client with private key
    client = Client(api_key, api_secret, private_key)

Requests Settings
-----------------

`python-idex` uses the `requests <http://docs.python-requests.org/>`_ library and the
`aiohttp <https://aiohttp.readthedocs.io/>`_ library.

You can set custom requests parameters for all API calls when creating the client.

.. code:: python

    # for non-asyncio
    client = Client(address, private_key, {"verify": False, "timeout": 20})

    # for asyncio
    client = Client(address, private_key, {"verify_ssl": False, "timeout": 20})

You may also pass custom requests parameters through any API call to override default settings or the above settingsspecify new ones like the example below.

.. code:: python

    # this would result in verify: False and timeout: 5 for the get_ticker call
    client = Client(address, private_key, {"verify": False, "timeout": 20})
    client.get_ticker('ETH_SAN', requests_params={'timeout': 5})

Check out the `requests documentation <http://docs.python-requests.org/en/master/>`_ for all options.

**Proxy Settings**

You can use the Requests Settings method above

.. code:: python

    proxies = {
        'http': 'http://10.10.1.10:3128',
        'https': 'http://10.10.1.10:1080'
    }

    # in the Client instantiation
    client = Client(address, private_key, {'proxies': proxies})

    # or on an individual call
    client.get_ticker('ETH_SAN', requests_params={'proxies': proxies})

Or set an environment variable for your proxy if required to work across all requests.

An example for Linux environments from the `requests Proxies documentation <http://docs.python-requests.org/en/master/user/advanced/#proxies>`_ is as follows.

.. code-block:: bash

    $ export HTTP_PROXY="http://10.10.1.10:3128"
    $ export HTTPS_PROXY="http://10.10.1.10:1080"

For Windows environments

.. code-block:: bash

    C:\>set HTTP_PROXY=http://10.10.1.10:3128
    C:\>set HTTPS_PROXY=http://10.10.1.10:1080
