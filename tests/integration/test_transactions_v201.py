from __future__ import annotations

import asyncio

from ocpp.v201 import ChargePoint as Cp201
from ocpp.v201 import call
from ocpp.v201.enums import ConnectorStatusEnumType, TransactionEventEnumType, TriggerReasonEnumType
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer
from ocpp_bench.protocol import StationState


async def test_transaction_event_started_updated_ended(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-201-SESSION"
    async with connect(uri, subprotocols=[Subprotocol("ocpp2.0.1")]) as ws:
        cp = Cp201("CP-201-SESSION", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await cp.call(
                call.BootNotification(
                    charging_station={"vendor_name": "v", "model": "m"},
                    reason="PowerUp",
                )
            )
            await cp.call(
                call.StatusNotification(
                    timestamp="2026-10-09T12:00:00Z",
                    connector_status=ConnectorStatusEnumType.occupied.value,
                    evse_id=1,
                    connector_id=1,
                )
            )
            await cp.call(
                call.TransactionEvent(
                    event_type=TransactionEventEnumType.started.value,
                    timestamp="2026-10-09T12:00:00Z",
                    trigger_reason=TriggerReasonEnumType.authorized.value,
                    seq_no=0,
                    transaction_info={"transaction_id": "tx-1"},
                    evse={"id": 1, "connector_id": 1},
                    id_token={"id_token": "RFID-1", "type": "Central"},
                )
            )
            await cp.call(
                call.TransactionEvent(
                    event_type=TransactionEventEnumType.updated.value,
                    timestamp="2026-10-09T12:05:00Z",
                    trigger_reason=TriggerReasonEnumType.meter_value_periodic.value,
                    seq_no=1,
                    transaction_info={"transaction_id": "tx-1"},
                )
            )
            await cp.call(
                call.TransactionEvent(
                    event_type=TransactionEventEnumType.ended.value,
                    timestamp="2026-10-09T12:30:00Z",
                    trigger_reason=TriggerReasonEnumType.stop_authorized.value,
                    seq_no=2,
                    transaction_info={"transaction_id": "tx-1"},
                )
            )
        finally:
            pump.cancel()

    station = await server.store.get("CP-201-SESSION")
    assert station is not None
    assert station.protocol == "ocpp2.0.1"
    assert station.fsm.state in {StationState.FINISHING, StationState.DISCONNECTED}
