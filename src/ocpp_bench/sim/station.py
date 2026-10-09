from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call as call16
from ocpp.v16.enums import ChargePointErrorCode, ChargePointStatus
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed
from websockets.typing import Subprotocol

from ocpp_bench.logging import get_logger

logger = get_logger("sim.station")


@dataclass
class LatencySamples:
    boot: list[float] = field(default_factory=list)
    heartbeat: list[float] = field(default_factory=list)
    start_tx: list[float] = field(default_factory=list)

    def all(self) -> dict[str, list[float]]:
        return {"boot": self.boot, "heartbeat": self.heartbeat, "start_tx": self.start_tx}


@dataclass
class VirtualStation:
    charge_point_id: str
    target: str  # e.g. "ws://localhost:9000/ocpp"
    protocol: str = "ocpp1.6"
    reconnects: int = 0
    latency: LatencySamples = field(default_factory=LatencySamples)

    def _uri(self) -> str:
        return f"{self.target.rstrip('/')}/{self.charge_point_id}"

    @asynccontextmanager
    async def _connected(self) -> AsyncIterator[Cp16]:
        async with connect(
            self._uri(),
            subprotocols=[Subprotocol(self.protocol)],
            open_timeout=10,
            ping_interval=20,
            ping_timeout=20,
        ) as ws:
            cp = Cp16(self.charge_point_id, ws)
            pump = asyncio.create_task(cp.start())
            try:
                yield cp
            finally:
                pump.cancel()

    async def boot(self, cp: Cp16) -> None:
        started = time.monotonic()
        await cp.call(
            call16.BootNotification(charge_point_vendor="ocpp-bench", charge_point_model="sim")
        )
        self.latency.boot.append(time.monotonic() - started)

    async def heartbeat(self, cp: Cp16) -> None:
        started = time.monotonic()
        await cp.call(call16.Heartbeat())
        self.latency.heartbeat.append(time.monotonic() - started)

    async def status(self, cp: Cp16, connector_id: int, status: ChargePointStatus) -> None:
        await cp.call(
            call16.StatusNotification(
                connector_id=connector_id,
                error_code=ChargePointErrorCode.no_error,
                status=status,
            )
        )

    async def start_transaction(
        self, cp: Cp16, connector_id: int, id_tag: str, meter_start: int = 0
    ) -> int:
        started = time.monotonic()
        result = await cp.call(
            call16.StartTransaction(
                connector_id=connector_id,
                id_tag=id_tag,
                meter_start=meter_start,
                timestamp=_now_iso(),
            )
        )
        self.latency.start_tx.append(time.monotonic() - started)
        return int(result.transaction_id)

    async def meter_values(
        self, cp: Cp16, connector_id: int, transaction_id: int, meter_wh: int
    ) -> None:
        await cp.call(
            call16.MeterValues(
                connector_id=connector_id,
                meter_value=[
                    {
                        "timestamp": _now_iso(),
                        "sampled_value": [{"value": str(meter_wh), "unit": "Wh"}],
                    }
                ],
                transaction_id=transaction_id,
            )
        )

    async def stop_transaction(self, cp: Cp16, transaction_id: int, meter_stop: int) -> None:
        await cp.call(
            call16.StopTransaction(
                meter_stop=meter_stop,
                timestamp=_now_iso(),
                transaction_id=transaction_id,
            )
        )

    @asynccontextmanager
    async def connected(self) -> AsyncIterator[Cp16]:
        try:
            async with self._connected() as cp:
                yield cp
        except ConnectionClosed as exc:
            logger.warning("sim connection closed", cp_id=self.charge_point_id, reason=repr(exc))


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
