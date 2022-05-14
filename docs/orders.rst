Order Endpoints
===============

These functions use the wallet address passed in the constructor.

`create_order` is the most flexible allow all types of orders, see IDEX documentation
for more info.

.. autoclass:: idex.client.Client
    :members: create_order, create_market_order, create_limit_order, cancel_orders, cancel_order, get_my_open_orders, get_my_trade_history, get_order_trades
    :noindex:
    :member-order: bysource
