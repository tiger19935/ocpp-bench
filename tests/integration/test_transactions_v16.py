from __future__ import annotations

import asyncio

from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call
from ocpp.v16.enums import AuthorizationStatus, ChargePointErrorCode, ChargePointStatus
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer
from ocpp_bench.protocol import StationState


async def test_full_session_1_6(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-SESSION"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = Cp16("CP-SESSION", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await cp.call(call.BootNotification(charge_point_vendor="v", charge_point_model="m"))
            await cp.call(
                call.StatusNotification(
                    connector_id=1,
                    error_code=ChargePointErrorCode.no_error,
                    status=ChargePointStatus.preparing,
                )
            )
            auth = await cp.call(call.Authorize(id_tag="RFID-1"))
            assert auth.id_tag_info["status"] == AuthorizationStatus.accepted.value

            start = await cp.call(
                call.StartTransaction(
                    connector_id=1,
                    id_tag="RFID-1",
                    meter_start=0,
                    timestamp="2026-10-09T12:00:00Z",
                )
            )
            txn_id = start.transaction_id
            assert txn_id >= 1
            assert start.id_tag_info["status"] == AuthorizationStatus.accepted.value

            await cp.call(
                call.MeterValues(
                    connector_id=1,
                    meter_value=[
                        {
                            "timestamp": "2026-10-09T12:00:30Z",
                            "sampled_value": [{"value": "0.5", "unit": "kWh"}],
                        }
                    ],
                    transaction_id=txn_id,
                )
            )
            stop = await cp.call(
                call.StopTransaction(
                    meter_stop=1500,
                    timestamp="2026-10-09T12:30:00Z",
                    transaction_id=txn_id,
                )
            )
            assert stop.id_tag_info["status"] == AuthorizationStatus.accepted.value
        finally:
            pump.cancel()

    station = await server.store.get("CP-SESSION")
    assert station is not None
    assert station.fsm.state in {StationState.FINISHING, StationState.DISCONNECTED}
    assert await server.sessions.get(1) is None
