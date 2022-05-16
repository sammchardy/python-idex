from typing import Dict, Tuple, Any

from idex.enums import OrderType, OrderSide, OrderTimeInForce, OrderSelfTradePrevention

ORDER_TYPE_MAP = {
    OrderType.MARKET: 0,
    OrderType.LIMIT: 1,
    OrderType.LIMIT_MAKER: 2,
    OrderType.STOP_LOSS: 3,
    OrderType.STOP_LOSS_LIMIT: 4,
    OrderType.TAKE_PROFIT: 5,
    OrderType.TAKE_PROFIT_LIMIT: 6,
}

ORDER_SIDE_MAP = {
    OrderSide.BUY: 0,
    OrderSide.SELL: 1,
}

ORDER_TIME_IN_FORCE_MAP = {
    OrderTimeInForce.GOOD_TILL_CANCEL: 0,
    OrderTimeInForce.IMMEDIATE_OR_CANCEL: 2,
    OrderTimeInForce.FILL_OR_KILL: 3,
}

ORDER_SELF_TRADE_PREVENTION_MAP = {
    OrderSelfTradePrevention.DECREMENT_AND_CANCEL: 0,
    OrderSelfTradePrevention.CANCEL_OLDEST: 1,
    OrderSelfTradePrevention.CANCEL_NEWEST: 2,
    OrderSelfTradePrevention.CANCEL_BOTH: 3,
}

SigParamType = Tuple[Tuple[str, Any], ...]


def path_signature_parameters(
    path: str, method: str, wallet_address: str, sandbox: bool, data: Dict
) -> SigParamType:
    param_func_map = {
        "wallets-post": wallet_sign_associate_wallet,
        "orders-post": wallet_sign_create_order,
        "orders/test-post": wallet_sign_create_order,
        "orders-delete": wallet_sign_cancel_order,
        "orders/test-delete": wallet_sign_cancel_order,
        "withdrawals-post": wallet_sign_associate_wallet,
        "addLiquidity-post": wallet_sign_add_liquidity,
        "removeLiquidity-post": wallet_sign_remove_liquidity,
    }

    param_func = param_func_map.get(f"{path}-{method}")
    if param_func:
        return param_func(wallet_address, sandbox, data)
    raise Exception(f'Unknown signed path {method.upper()} {path}')


def wallet_sign_associate_wallet(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    return (
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
    )


def wallet_sign_create_order(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    quantity = data.get("quantity") or data.get("quantityInQuote")
    quantity_in_quote = data.get("quantity") is None
    return (
        ("uint8", 104 if sandbox else 4),
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
        ("string", data["market"]),
        ("uint8", ORDER_TYPE_MAP[data["type"]]),
        ("uint8", ORDER_SIDE_MAP[data["side"]]),
        ("string", quantity),
        ("bool", quantity_in_quote),
        ("string", data.get("price", "")),
        ("string", data.get("stopPrice", "")),
        ("string", data.get("clientOrderId", "")),
        (
            "uint8",
            ORDER_TIME_IN_FORCE_MAP[data.get("timeInForce", OrderTimeInForce.GOOD_TILL_CANCEL)],
        ),
        (
            "uint8",
            ORDER_SELF_TRADE_PREVENTION_MAP[
                data.get("selfTradePrevention", OrderSelfTradePrevention.DECREMENT_AND_CANCEL)
            ],
        ),
        ("uint64", 0),
    )


def wallet_sign_cancel_order(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    order_id = data.get("orderId") if not data.get("market") else ""
    market = data.get("market") if not data.get("orderId") else ""
    return (
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
        ("string", order_id),
        ("string", market),
    )


def wallet_sign_withdraw_funds(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    return (
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
        ("string", data.get("asset", "")),
        ("address", data.get("asset_contract_address", "")),
        ("string", data["quantity"]),
        ("bool", True),
    )


def wallet_sign_add_liquidity(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    return (
        ("uint8", 104 if sandbox else 4),
        ("uint8", 0),  # addition
        ("uint8", 1),  # off chain
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
        ("address", data["tokenAContractAddress"]),
        ("address", data["tokenBContractAddress"]),
        ("uint256", int(data["amountADesired"])),
        ("uint256", int(data["amountBDesired"])),
        ("uint256", int(data["amountAMin"])),
        ("uint256", int(data["amountBMin"])),
        ("address", data["to"]),
        ("uint64", 0),
    )


def wallet_sign_remove_liquidity(wallet_address: str, sandbox: bool, data: Dict) -> SigParamType:
    return (
        ("uint8", 104 if sandbox else 4),
        ("uint8", 1),  # removal
        ("uint8", 1),  # off chain
        ("uint128", data["nonce"].int),
        ("address", wallet_address),
        ("address", data["tokenAContractAddress"]),
        ("address", data["tokenBContractAddress"]),
        ("uint256", int(data["liquidity"])),
        ("uint256", int(data["amountAMin"])),
        ("uint256", int(data["amountBMin"])),
        ("address", data["to"]),
        ("uint64", 0),
    )
