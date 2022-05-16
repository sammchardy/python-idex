from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CandleInterval(str, Enum):
    MINUTES_1 = "1m"
    MINUTES_5 = "5m"
    MINUTES_15 = "15m"
    MINUTES_30 = "30m"
    HOURS_1 = "1h"
    HOURS_6 = "6h"
    DAYS_1 = "1d"


class OrderbookLevel(int, Enum):
    LEVEL_1 = 1
    LEVEL_2 = 2


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    LIMIT_MAKER = "limitMaker"
    STOP_LOSS = "stopLoss"
    STOP_LOSS_LIMIT = "stopLossLimit"
    TAKE_PROFIT = "takeProfit"
    TAKE_PROFIT_LIMIT = "takeProfitLimit"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderTimeInForce(str, Enum):
    GOOD_TILL_CANCEL = "gtc"
    IMMEDIATE_OR_CANCEL = "ioc"
    FILL_OR_KILL = "fok"


class OrderSelfTradePrevention(str, Enum):
    DECREMENT_AND_CANCEL = "dc"
    CANCEL_OLDEST = "co"
    CANCEL_NEWEST = "cn"
    CANCEL_BOTH = "cb"


class SignType(Enum):
    USER = "user"
    TRADE = "trade"


@dataclass
class TransactionOptions:
    gas: Optional[int] = None
    gas_price: Optional[int] = None

    def to_dict(self):
        result = {}
        if self.gas:
            result['gas'] = self.gas
        if self.gas_price:
            result['gasPrice'] = self.gas_price
        return result
