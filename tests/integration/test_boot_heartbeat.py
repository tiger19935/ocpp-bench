from __future__ import annotations

import asyncio

from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call as call16
from ocpp.v16.enums import RegistrationStatus
from ocpp.v201 import ChargePoint as Cp201
from ocpp.v201 import call as call201
from ocpp.v201.enums import RegistrationStatusEnumType
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer
from ocpp_bench.protocol import StationState


async def test_boot_and_heartbeat_v16(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-16"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = Cp16("CP-16", ws)
        task = asyncio.create_task(cp.start())
        try:
            boot_resp = await asyncio.wait_for(
                cp.call(call16.BootNotification(charge_point_vendor="v", charge_point_model="m")),
                timeout=5,
            )
            assert boot_resp.status == RegistrationStatus.accepted
            hb_resp = await asyncio.wait_for(cp.call(call16.Heartbeat()), timeout=5)
            assert hb_resp.current_time
        finally:
            task.cancel()

    station = await server.store.get("CP-16")
    assert station is not None
    assert station.fsm.state in {StationState.AVAILABLE, StationState.DISCONNECTED}


async def test_boot_and_heartbeat_v201(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-201"
    async with connect(uri, subprotocols=[Subprotocol("ocpp2.0.1")]) as ws:
        cp = Cp201("CP-201", ws)
        task = asyncio.create_task(cp.start())
        try:
            boot_resp = await asyncio.wait_for(
                cp.call(
                    call201.BootNotification(
                        charging_station={"vendor_name": "v", "model": "m"},
                        reason="PowerUp",
                    )
                ),
                timeout=5,
            )
            assert boot_resp.status == RegistrationStatusEnumType.accepted
            hb_resp = await asyncio.wait_for(cp.call(call201.Heartbeat()), timeout=5)
            assert hb_resp.current_time
        finally:
            task.cancel()

    station = await server.store.get("CP-201")
    assert station is not None
    assert station.protocol == "ocpp2.0.1"
