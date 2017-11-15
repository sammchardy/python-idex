#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexCurrencyNotFoundException
import pytest
import requests_mock


client = Client()

currency_res = {
    "ETH": {
        "decimals": 18,
        "address": '0x0000000000000000000000000000000000000000',
        "name": 'Ether'
    },
    "REP": {
        "decimals": 8,
        "address": '0xc853ba17650d32daba343294998ea4e33e7a48b9',
        "name": 'Reputation'
    },
    "DVIP": {
        "decimals": 8,
        "address": '0xf59fad2879fb8380ffa6049a48abf9c9959b3b5c',
        "name": 'Aurora'
    }
}


def test_valid_currency():
    """Test valid currency"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnCurrencies', json=currency_res, status_code=200)
        client.get_currency('ETH')


def test_invalid_currency():
    """Test invalid currency"""

    with pytest.raises(IdexCurrencyNotFoundException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/returnCurrencies', json=currency_res, status_code=200)
            client.get_currency('NOTFOUND')
