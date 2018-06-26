#!/usr/bin/env python
# coding=utf-8

import asyncio
import pytest
from aioresponses import aioresponses
from idex.asyncio import AsyncClient
from idex.exceptions import IdexAPIException, IdexRequestException


def test_invalid_json():
    """Test Invalid response Exception"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.post('https://api.idex.market/returnTicker', body='<head></html>')

        async def _run_test():
            client = await AsyncClient.create()
            with pytest.raises(IdexRequestException):
                await client.get_tickers()

        loop.run_until_complete(_run_test())


def test_api_exception():
    """Test API response Exception"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        json_obj = {
            "error": "Signature verification failed"
        }
        m.post('https://api.idex.market/returnOrderBook', payload=json_obj, status=200)

        async def _run_test():
            client = await AsyncClient.create()
            with pytest.raises(IdexAPIException):
                await client.get_order_books()

        loop.run_until_complete(_run_test())
