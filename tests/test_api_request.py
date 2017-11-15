#!/usr/bin/env python
# coding=utf-8

from idex.client import Client
from idex.exceptions import IdexAPIException, IdexRequestException
import pytest
import requests_mock


client = Client()


def test_invalid_json():
    """Test Invalid response Exception"""

    with pytest.raises(IdexRequestException):
        with requests_mock.mock() as m:
            m.post('https://api.idex.market/returnTicker', text='<head></html>')
            client.get_tickers()


def test_api_exception():
    """Test API response Exception"""

    with pytest.raises(IdexAPIException):
        with requests_mock.mock() as m:
            json_obj = {
                "error": "Signature verification failed"
            }
            m.post('https://api.idex.market/returnOrderBook', json=json_obj, status_code=200)
            client.get_order_books()
