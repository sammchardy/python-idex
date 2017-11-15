#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexWalletAddressNotFoundException
import pytest
import requests_mock

json_res = {}


def test_wallet_address_set():
    """Test valid currency"""

    client = Client('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2')

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnNextNonce', json=json_res, status_code=200)
        client.get_my_next_nonce()


def test_wallet_address_not_set():
    """Test invalid currency"""

    client = Client()
    with pytest.raises(IdexWalletAddressNotFoundException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/returnNextNonce', json=json_res, status_code=200)
            client.get_my_next_nonce()
