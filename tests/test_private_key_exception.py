#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexPrivateKeyNotFoundException
import pytest
import requests_mock

json_res = {}


def test_private_key_set():
    """Test valid currency"""

    client = Client('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2', '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

    with requests_mock.mock() as m:
        m.post('https://api.idex.market/cancel', json=json_res, status_code=200)
        client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')


def test_private_key_not_set():
    """Test invalid currency"""

    client = Client('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2')
    with pytest.raises(IdexPrivateKeyNotFoundException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/cancel', json=json_res, status_code=200)
            client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')
