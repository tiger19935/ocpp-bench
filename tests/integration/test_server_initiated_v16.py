from __future__ import annotations

import asyncio
from typing import Any

from ocpp.routing import on
from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RemoteStartStopStatus, ResetStatus
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer
from ocpp_bench.csms.connection import CsmsChargePointV16


class _Compliant(Cp16):  # type: ignore[misc]
    def __init__(self, cp_id: str, ws: object) -> None:
        super().__init__(cp_id, ws)
        self.remote_starts: list[dict[str, Any]] = []
        self.remote_stops: list[int] = []
        self.resets: list[str] = []
        self.config_changes: list[tuple[str, str]] = []

    @on(Action.remote_start_transaction)
    async def on_remote_start(
        self, id_tag: str, connector_id: int | None = None, **_: Any
    ) -> call_result.RemoteStartTransaction:
        self.remote_starts.append({"id_tag": id_tag, "connector_id": connector_id})
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)

    @on(Action.remote_stop_transaction)
    async def on_remote_stop(
        self, transaction_id: int, **_: Any
    ) -> call_result.RemoteStopTransaction:
        self.remote_stops.append(transaction_id)
        return call_result.RemoteStopTransaction(status=RemoteStartStopStatus.accepted)

    @on(Action.reset)
    async def on_reset(self, type: str, **_: Any) -> call_result.Reset:  # noqa: A002
        self.resets.append(type)
        return call_result.Reset(status=ResetStatus.accepted)

    @on(Action.get_configuration)
    async def on_get_cfg(
        self, key: list[str] | None = None, **_: Any
    ) -> call_result.GetConfiguration:
        return call_result.GetConfiguration(
            configuration_key=[{"key": "HeartbeatInterval", "readonly": False, "value": "60"}],
            unknown_key=list(key or []),
        )

    @on(Action.change_configuration)
    async def on_change_cfg(
        self, key: str, value: str, **_: Any
    ) -> call_result.ChangeConfiguration:
        self.config_changes.append((key, value))
        return call_result.ChangeConfiguration(status="Accepted")


async def test_remote_start_stop_reset_and_configuration(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-REMOTE"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = _Compliant("CP-REMOTE", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await cp.call(call.BootNotification(charge_point_vendor="v", charge_point_model="m"))
            for _ in range(50):
                live = server.get_connection("CP-REMOTE")
                if live is not None:
                    break
                await asyncio.sleep(0.01)
            assert isinstance(live, CsmsChargePointV16)

            start_resp = await live.remote_start("RFID-X", connector_id=1)
            stop_resp = await live.remote_stop(transaction_id=42)
            reset_resp = await live.reset()
            cfg_resp = await live.get_configuration(key=["HeartbeatInterval"])
            change_resp = await live.change_configuration("HeartbeatInterval", "30")
        finally:
            pump.cancel()

    assert start_resp.status == RemoteStartStopStatus.accepted.value
    assert stop_resp.status == RemoteStartStopStatus.accepted.value
    assert reset_resp.status == ResetStatus.accepted.value
    assert cfg_resp.configuration_key[0]["key"] == "HeartbeatInterval"
    assert change_resp.status == "Accepted"
    assert cp.remote_starts == [{"id_tag": "RFID-X", "connector_id": 1}]
    assert cp.remote_stops == [42]
    assert cp.resets == ["Soft"]
    assert cp.config_changes == [("HeartbeatInterval", "30")]
