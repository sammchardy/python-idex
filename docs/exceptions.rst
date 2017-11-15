Exceptions
==========

IdexException
-------------

Raised if a wallet address or private key are not set

IdexCurrencyNotFoundException
-----------------------------

Raised if a requested currency is not found

IdexResponseException
-----------------------

Raised if a non JSON response is returned

IdexAPIException
------------------

On an API call error a idex.exceptions.IdexAPIException will be raised.

The exception provides access to the

- `status_code` - response status code
- `response` - response object
- `message` - IDEX error message
- `request` - request object if available

.. code:: python

    try:
        client.get_currencies()
    except IdexAPIException as e:
        print(e.status_code)
        print(e.message)

