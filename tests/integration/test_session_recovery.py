from __future__ import annotations

import asyncio

from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call
from ocpp.v16.enums import AuthorizationStatus
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer


async def _boot(cp: Cp16) -> None:
    await cp.call(call.BootNotification(charge_point_vendor="v", charge_point_model="m"))


async def test_reconnect_resumes_transaction(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-REC"

    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = Cp16("CP-REC", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await _boot(cp)
            start = await cp.call(
                call.StartTransaction(
                    connector_id=1,
                    id_tag="RFID",
                    meter_start=0,
                    timestamp="2026-10-09T00:00:00Z",
                )
            )
            txn_id = start.transaction_id
            assert await server.sessions.get(txn_id) is not None
        finally:
            pump.cancel()

    # SessionStore survives the disconnect.
    assert await server.sessions.get(txn_id) is not None

    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = Cp16("CP-REC", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await _boot(cp)
            stop = await cp.call(
                call.StopTransaction(
                    meter_stop=1000,
                    timestamp="2026-10-09T00:10:00Z",
                    transaction_id=txn_id,
                )
            )
            assert stop.id_tag_info["status"] == AuthorizationStatus.accepted.value
        finally:
            pump.cancel()

    assert await server.sessions.get(txn_id) is None
    station = await server.store.get("CP-REC")
    assert station is not None
    assert station.reconnects == 1


async def test_late_stop_for_unknown_transaction_is_accepted(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-LATE"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = Cp16("CP-LATE", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await _boot(cp)
            stop = await cp.call(
                call.StopTransaction(
                    meter_stop=1,
                    timestamp="2026-10-09T00:10:00Z",
                    transaction_id=9999,
                )
            )
            assert stop.id_tag_info["status"] == AuthorizationStatus.accepted.value
        finally:
            pump.cancel()
