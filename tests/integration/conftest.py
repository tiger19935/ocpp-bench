from __future__ import annotations

import asyncio
import contextlib
import socket
from collections.abc import AsyncIterator

import pytest_asyncio

from ocpp_bench.config import Protocol, Settings
from ocpp_bench.csms import CsmsServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest_asyncio.fixture
async def csms_server() -> AsyncIterator[tuple[CsmsServer, int, asyncio.Task[None]]]:
    port = _free_port()
    settings = Settings(host="127.0.0.1", port=port, protocol=Protocol.BOTH, log_json=False)
    server = CsmsServer.from_settings(settings)
    stop: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    task = asyncio.create_task(server.serve(stop))
    for _ in range(50):
        try:
            w = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            w.settimeout(0.05)
            w.connect(("127.0.0.1", port))
            w.close()
            break
        except OSError:
            await asyncio.sleep(0.02)
    try:
        yield server, port, task
    finally:
        if not stop.done():
            stop.set_result(None)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
