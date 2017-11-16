Order Endpoints
===============

These functions use the wallet address passed in the constructor.

.. autoclass:: idex.client.Client
    :members: create_order, create_trade, cancel_order, get_my_open_orders, get_my_trade_history, get_order_trades
    :noindex:
    :member-order: bysource

These functions take an address, typically you would only use them to fetch from your own address.

.. autoclass:: idex.client.Client
    :members: get_open_orders, get_trade_history
    :noindex:
    :member-order: bysource
