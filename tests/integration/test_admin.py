from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from ocpp.routing import on
from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call, call_result
from ocpp.v16.enums import Action, RemoteStartStopStatus
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.csms import CsmsServer


class _Compliant(Cp16):  # type: ignore[misc]
    @on(Action.remote_start_transaction)
    async def on_remote_start(self, **_: Any) -> call_result.RemoteStartTransaction:
        return call_result.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)


async def test_metrics_endpoint_renders_prometheus(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, _, _ = csms_server
    async with aiohttp.ClientSession() as http:
        url = f"http://127.0.0.1:{server.settings.admin_port}/metrics"
        async with http.get(url) as resp:
            assert resp.status == 200
            body = await resp.text()
    assert "ocpp_bench_stations_connected" in body


async def test_stations_endpoint_and_remote_start(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    uri = f"ws://127.0.0.1:{port}/ocpp/CP-ADMIN"
    async with connect(uri, subprotocols=[Subprotocol("ocpp1.6")]) as ws:
        cp = _Compliant("CP-ADMIN", ws)
        pump = asyncio.create_task(cp.start())
        try:
            await cp.call(call.BootNotification(charge_point_vendor="v", charge_point_model="m"))

            for _ in range(50):
                if server.get_connection("CP-ADMIN") is not None:
                    break
                await asyncio.sleep(0.02)

            async with aiohttp.ClientSession() as http:
                base = f"http://127.0.0.1:{server.settings.admin_port}"
                async with http.get(f"{base}/stations") as resp:
                    assert resp.status == 200
                    data = await resp.json()
                assert any(s["charge_point_id"] == "CP-ADMIN" for s in data["stations"])

                async with http.post(
                    f"{base}/stations/CP-ADMIN/remote-start",
                    json={"id_tag": "RFID-ADMIN", "connector_id": 1},
                ) as resp:
                    assert resp.status == 200
                    body = await resp.json()
                assert body["status"] == RemoteStartStopStatus.accepted.value

                async with http.post(
                    f"{base}/stations/CP-NOT-THERE/remote-start",
                    json={"id_tag": "RFID", "connector_id": 1},
                ) as resp:
                    assert resp.status == 404
        finally:
            pump.cancel()
