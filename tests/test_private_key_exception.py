#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexException, IdexPrivateKeyNotFoundException
import pytest
import requests_mock

json_res = {}

api_key = 'api:jVXLd5h1bEYcKgZbQru2k'
address = '0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2'
private_key = '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52'


def test_private_key_set():
    """Test private key is set"""

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/returnNextNonce', json={'nonce': 1}, status_code=200)
        m.post('https://api.idex.market/cancel', json=json_res, status_code=200)
        client = Client(api_key, address, private_key)
        client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')


def test_private_key_not_set():
    """Test private key not set"""

    with pytest.raises(IdexPrivateKeyNotFoundException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/returnNextNonce', json={'nonce': 1}, status_code=200)
            m.post('https://api.idex.market/cancel', json=json_res, status_code=200)
            client = Client(api_key, address)
            client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')
