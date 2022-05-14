import asyncio
import re

from aioresponses import aioresponses
import pytest
import requests_mock

from idex import Client, AsyncClient
from idex.exceptions import IdexAPIException, IdexRequestException


def test_invalid_json():
    """Test Invalid response Exception"""

    client = Client()
    with pytest.raises(IdexRequestException):
        with requests_mock.mock() as m:
            m.get("https://api-matic.idex.io/v1/tickers", text="<head></html>")
            client.get_tickers()


def test_api_exception():
    """Test API response Exception"""

    client = Client()
    with pytest.raises(IdexAPIException, match="is required"):
        with requests_mock.mock() as m:
            json_obj = {
                "code": "REQUIRED_PARAMETER",
                "message": 'parameter "market" is required but was not provided',
            }
            m.get("https://api-matic.idex.io/v1/orderbook", json=json_obj, status_code=400)
            client.get_order_book(market="ETH-USDC")


def test_async_invalid_json():
    """Test Invalid response Exception"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.get("https://api-matic.idex.io/v1/tickers", body="<head></html>")

        async def _run_test():
            client = await AsyncClient.create()
            with pytest.raises(IdexRequestException):
                await client.get_tickers()

        loop.run_until_complete(_run_test())


def test_async_api_exception():
    """Test API response Exception"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        json_obj = {
            "code": "REQUIRED_PARAMETER",
            "message": 'parameter "market" is required but was not provided',
        }
        m.get(
            re.compile(r"^https://api-matic.idex.io/v1/orderbook.*$"), payload=json_obj, status=400
        )

        async def _run_test():
            client = await AsyncClient.create()
            with pytest.raises(IdexAPIException):
                await client.get_order_book(market="ETH-USDC")

        loop.run_until_complete(_run_test())
