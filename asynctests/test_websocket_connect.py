#!/usr/bin/env python
# coding=utf-8

import asyncio
from idex.asyncio import IdexSocketManager

api_key = 'api:jVXLd5h1bEYcKgZbQru2k'


def test_websocket_connect():
    """Test Connecting Websocket"""

    loop = asyncio.get_event_loop()

    async def _run_test():
        async def handle_evt(_msg):
            pass

        await IdexSocketManager.create(loop=loop, callback=handle_evt, api_key=api_key)

    loop.run_until_complete(_run_test())

