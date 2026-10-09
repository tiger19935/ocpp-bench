from __future__ import annotations

import asyncio
from typing import Any

import pytest
from ocpp.routing import on
from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RemoteStartStopStatus
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer
from ocpp_bench.protocol import CallTimeout, StationState


class _SlowCp(Cp16):  # type: ignore[misc]
    def __init__(self, cp_id: str, ws: object, delay: float) -> None:
        super().__init__(cp_id, ws)
        self._delay = delay

    @on(Action.remote_start_transaction)
    async def on_remote_start(self, **_: Any) -> call_result.RemoteStartTransaction:
        await asyncio.sleep(self._delay)
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)


async def test_remote_start_times_out_and_marks_unresponsive(
    csms_short_timeout: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_short_timeout
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-SLOW"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = _SlowCp("CP-SLOW", ws, delay=1.5)
        pump = asyncio.create_task(cp.start())
        try:
            await cp.call(call.BootNotification(charge_point_vendor="v", charge_point_model="m"))
            for _ in range(50):
                live = server.get_connection("CP-SLOW")
                if live is not None:
                    break
                await asyncio.sleep(0.01)
            assert live is not None

            with pytest.raises(CallTimeout) as exc:
                await live.remote_start("RFID-X")  # type: ignore[union-attr]
            assert exc.value.action == "RemoteStartTransaction"
        finally:
            pump.cancel()

    station = await server.store.get("CP-SLOW")
    assert station is not None
    assert station.fsm.state in {StationState.UNRESPONSIVE, StationState.DISCONNECTED}
