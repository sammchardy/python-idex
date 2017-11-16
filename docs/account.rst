Account Endpoints
=================

These functions use the wallet address passed in the constructor.

.. autoclass:: idex.client.Client
    :members: get_my_balances, get_my_transfers, get_my_next_nonce
    :noindex:
    :member-order: bysource

These functions take an address, typically it's simpler to use the above functions.

.. autoclass:: idex.client.Client
    :members: get_balances, get_transfers, get_next_nonce
    :noindex:
    :member-order: bysource
