#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexWalletAddressNotFoundException
import pytest
import requests_mock

api_key = 'api:jVXLd5h1bEYcKgZbQru2k'
address = '0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2'


def test_wallet_address_set():

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnNextNonce', json={'nonce': 1}, status_code=200)
        client = Client(api_key, address)
        client.get_my_next_nonce()


def test_wallet_address_not_set():

    client = Client(api_key)
    with pytest.raises(IdexWalletAddressNotFoundException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/returnNextNonce', json={}, status_code=200)
            client.get_my_next_nonce()
