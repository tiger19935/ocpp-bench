from __future__ import annotations

import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator

import pytest_asyncio
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.config import Protocol, Settings
from ocpp_bench.csms import CsmsServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest_asyncio.fixture
async def small_queue_csms() -> AsyncIterator[tuple[CsmsServer, int]]:
    port = _free_port()
    settings = Settings(
        host="127.0.0.1",
        port=port,
        protocol=Protocol.V16,
        log_json=False,
        inbound_queue_depth=4,
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
        yield server, port
    finally:
        if not stop.done():
            stop.set_result(None)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


async def test_queue_overflow_returns_callerror_and_increments_drop_counter(
    small_queue_csms: tuple[CsmsServer, int],
) -> None:
    server, port = small_queue_csms
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-FLOOD"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        # Send a flood of Heartbeat Calls without reading responses in between
        # so the inbound queue fills up on the server. The server's reader
        # task will put at most queue_depth items, then start sending
        # CALLERROR InboundQueueFull for the rest.
        for i in range(50):
            call = [2, f"id-{i}", "Heartbeat", {}]
            await ws.send(json.dumps(call))

        got_errors = 0
        got_results = 0
        for _ in range(50):
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
            msg = json.loads(raw)
            if msg[0] == 4 and msg[2] == "InternalError" and msg[3] == "InboundQueueFull":
                got_errors += 1
            elif msg[0] == 3:
                got_results += 1

    station = await server.store.get("CP-FLOOD")
    assert station is not None
    assert station.queue_drops == got_errors
    assert got_errors > 0
    assert got_results > 0
