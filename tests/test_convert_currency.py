#!/usr/bin/env python
# coding=utf-8

from decimal import *

from idex.client import Client
from idex.exceptions import IdexAPIException, IdexRequestException
import pytest
import requests_mock


client = Client()

currencies_json = {
    "ETH": {
        "name": "Ether",
        "decimals": 18,
        "address": "0x0000000000000000000000000000000000000000"
    },
    "EAGLE": {
        "name": "Eagle",
        "address": "0x0000000000000000000000000000000000000000"
    },

}

examples = [
    ['ETH', '3100000000000000000000', 3100],
    ['ETH', '400000000000000000', 0.4],
    ['ETH', '1', 0.000000000000000001],
    ['ETH', '8', 0.000000000000000008],
    ['ETH', '888', 0.000000000000000888],
    ['ETH', '32425253645663458', '0.032425253645663458'],
    ['ETH', '32425253645663452', Decimal('0.032425253645663452')],
    ['ETH', '32425253645663452', '0.032425253645663452'],
]

not_found_examples = [
    ['BTC', '3100000000000000000000', 3100],
]

no_decimals_examples = [
    ['EAGLE', '3100000000000000000000', 3100],
    ['EAGLE', '400000000000000000', 0.4],
    ['EAGLE', '1', 0.000000000000000001],
    ['EAGLE', '8', 0.000000000000000008],
    ['EAGLE', '888', 0.000000000000000888],
    ['EAGLE', '32425253645663458', '0.032425253645663458'],
    ['EAGLE', '32425253645663452', Decimal('0.032425253645663452')],
    ['EAGLE', '32425253645663452', '0.032425253645663452'],
]


def test_convert_to_currency_valid():
    """Test Convert to currency is valid"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in examples:
            q = client.convert_to_currency_quantity(e[0], e[2])

            assert q == e[1]


def test_convert_from_currency_valid():
    """Test Convert from currency is valid"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in examples:
            q = client.parse_from_currency_quantity(e[0], e[1])

            val = '{}'.format(e[2])

            assert Decimal('0') == getcontext().compare(q, Decimal(val))


def test_convert_to_currency_not_found():
    """Test when currency is not found"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in not_found_examples:
            q = client.convert_to_currency_quantity(e[0], e[2])

            assert None is q


def test_convert_from_currency_not_found():
    """Test when currency is not found"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in not_found_examples:
            q = client.parse_from_currency_quantity(e[0], e[1])

            assert None is q


def test_convert_to_currency_no_decimals():
    """Test when currency is not found"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in no_decimals_examples:
            q = client.convert_to_currency_quantity(e[0], e[2])

            f_q = e[2]
            if type(e[2]) == float:
                f_q = Decimal(repr(e[2]))
            elif type(e[2]) == int:
                f_q = Decimal(e[2])
            elif type(e[2]) == str:
                f_q = Decimal(e[2])

            assert Decimal('0') == getcontext().compare(q, f_q)


def test_convert_from_currency_no_decimals():
    """Test when currency is not found"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currencies_json, status_code=200)

        for e in no_decimals_examples:
            q = client.parse_from_currency_quantity(e[0], e[1])

            assert Decimal('0') == getcontext().compare(q, Decimal(e[1]))
