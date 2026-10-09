from __future__ import annotations

import asyncio

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer


async def test_accepts_ocpp16_subprotocol(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-1"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        assert ws.subprotocol == "ocpp1.6"


async def test_accepts_ocpp201_subprotocol(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-2"
    async with connect(uri, subprotocols=[Subprotocol("ocpp2.0.1")]) as ws:
        assert ws.subprotocol == "ocpp2.0.1"


async def test_rejects_bad_path(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/nope/CP-3"
    with pytest.raises(InvalidStatus) as exc:
        async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]):
            pass
    assert exc.value.response.status_code == 404


async def test_rejects_unknown_subprotocol(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-4"
    with pytest.raises(InvalidStatus) as exc:
        async with connect(uri, subprotocols=[Subprotocol("not-a-real-one")]):
            pass
    # websockets rejects a non-matching subprotocol offer with 400.
    assert exc.value.response.status_code in (400, 404)
