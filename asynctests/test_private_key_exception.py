#!/usr/bin/env python
# coding=utf-8

import asyncio
import pytest
from aioresponses import aioresponses
from idex.asyncio import AsyncClient
from idex.exceptions import IdexException, IdexPrivateKeyNotFoundException

json_res = {}
nonce_res = {'nonce': 1}

api_key = 'api:jVXLd5h1bEYcKgZbQru2k'
address = '0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2'
private_key = '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52'


def test_private_key_set():
    """Test private key is set"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.post('https://api.idex.market/returnNextNonce', payload=nonce_res, status=200)
        m.post('https://api.idex.market/cancel', payload=json_res, status=200)

        async def _run_test():
            client = await AsyncClient.create(api_key, address, private_key)
            await client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

        loop.run_until_complete(_run_test())


def test_private_key_not_set():
    """Test private key not set"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.post('https://api.idex.market/returnNextNonce', payload=nonce_res, status=200)
        m.post('https://api.idex.market/cancel', payload=json_res, status=200)

        async def _run_test():
            client = await AsyncClient.create(api_key, address)
            with pytest.raises(IdexPrivateKeyNotFoundException):
                await client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

        loop.run_until_complete(_run_test())
