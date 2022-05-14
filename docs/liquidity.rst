Liquidity Endpoints
===================

Liquidity functions return amounts in token precision, use `idex.utils.parse_from_token_quantity` to
normalise

.. autoclass:: idex.client.Client
    :members: get_liquidity_pools, add_liquidity, remove_liquidity, get_liquidity_additions, get_liquidity_removals
    :noindex:
    :member-order: bysource
