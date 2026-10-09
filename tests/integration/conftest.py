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


async def _make_server(
    **overrides: object,
) -> tuple[CsmsServer, int, asyncio.Future[None], asyncio.Task[None]]:
    port = _free_port()
    admin_port = _free_port()
    base: dict[str, object] = {
        "host": "127.0.0.1",
        "port": port,
        "admin_port": admin_port,
        "protocol": Protocol.BOTH,
        "log_json": False,
    }
    base.update(overrides)
    settings = Settings(**base)  # type: ignore[arg-type]
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
    return server, port, stop, task


@pytest_asyncio.fixture
async def csms_server() -> AsyncIterator[tuple[CsmsServer, int, asyncio.Task[None]]]:
    port = _free_port()
    admin_port = _free_port()
    settings = Settings(
        host="127.0.0.1",
        port=port,
        admin_port=admin_port,
        protocol=Protocol.BOTH,
        log_json=False,
    )
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


@pytest_asyncio.fixture
async def csms_short_timeout() -> AsyncIterator[tuple[CsmsServer, int, asyncio.Task[None]]]:
    server, port, stop, task = await _make_server(call_timeout_sec=0.5)
    try:
        yield server, port, task
    finally:
        if not stop.done():
            stop.set_result(None)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
