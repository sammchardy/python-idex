#!/usr/bin/env python
# coding=utf-8

import asyncio
from idex.asyncio import IdexSocketManager


def test_websocket_connect():
    """Test Connecting Websocket"""

    loop = asyncio.get_event_loop()

    async def _run_test():
        ism = await IdexSocketManager.create(loop)

    loop.run_until_complete(_run_test())

