#!/usr/bin/env python
# coding=utf-8

import asyncio
import pytest
from aioresponses import aioresponses
from idex.asyncio import AsyncClient
from idex.exceptions import IdexException, IdexPrivateKeyNotFoundException

json_res = {}
nonce_res = { 'nonce': 1 }


def test_private_key_set():
    """Test private key is set"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.post('https://api.idex.market/returnNextNonce', payload=nonce_res, status=200)
        m.post('https://api.idex.market/cancel', payload=json_res, status=200)

        async def _run_test():
            client = await AsyncClient.create('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2', '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')
            await client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

        loop.run_until_complete(_run_test())


def test_private_key_not_set():
    """Test private key not set"""

    loop = asyncio.get_event_loop()
    with aioresponses() as m:
        m.post('https://api.idex.market/returnNextNonce', payload=nonce_res, status=200)
        m.post('https://api.idex.market/cancel', payload=json_res, status=200)

        async def _run_test():
            client = await AsyncClient.create('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2')
            with pytest.raises(IdexPrivateKeyNotFoundException):
                await client.cancel_order('0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc52')

        loop.run_until_complete(_run_test())


def test_private_key_invalid():
    """Test private key is not valid"""

    loop = asyncio.get_event_loop()
    keys = [
        '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc5'   # too short
        '0xcfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc555'  # too long
        '0xcxe4018c59ex0e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc555'  # invalid chars
        'aacfe4018c59e50e0e1964c979e6213ce5eb8c751cbc98a44251eb48a0985adc5'  # not prefix
    ]
    with aioresponses() as m:
        m.post('https://api.idex.market/returnNextNonce', payload=nonce_res, status=200)

        async def _run_test():
            with pytest.raises(IdexException):
                for key in keys:
                    client = await AsyncClient.create('0x926cfc20de3f3bdba2d6e7d75dbb1d0a3f93b9a2', key)

        loop.run_until_complete(_run_test())
