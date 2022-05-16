import uuid
from decimal import Decimal
from typing import Union, Dict


def get_nonce() -> uuid.UUID:
    return uuid.uuid1()


def format_quantity(quantity: Union[float, Decimal]):
    return f"{quantity:0.08f}"


def num_to_decimal(number) -> Decimal:
    if type(number) == float:
        number = Decimal(repr(number))
    elif type(number) == int:
        number = Decimal(number)
    elif type(number) == str:
        number = Decimal(number)

    return number


def parse_from_token_quantity(currency_details, quantity):
    if currency_details is None:
        return None

    f_q = Decimal(quantity)

    if "assetDecimals" not in currency_details:
        return f_q

    # divide by currency_details['decimals']
    d_str = "1{}".format(("0" * currency_details["assetDecimals"]))
    res = f_q / Decimal(d_str)

    return res


def convert_to_token_quantity(currency_details: Dict, quantity: float):
    f_q = num_to_decimal(quantity)

    if "assetDecimals" not in currency_details:
        return f_q

    # multiply by currency_details['assetDecimals']
    m_str = "1{}".format(("0" * currency_details["assetDecimals"]))
    res = (f_q * Decimal(m_str)).to_integral_exact()

    return "{:d}".format(int(res))
