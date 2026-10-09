from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import ClassVar, Literal

from ocpp.v16.enums import ChargePointStatus
from pydantic import BaseModel, ConfigDict, Field

from ocpp_bench.logging import get_logger
from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import LatencySamples, VirtualStation

logger = get_logger("sim.scenarios.normal")


class NormalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["normal"] = "normal"
    stations: int = Field(ge=1, le=10_000)
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    meter_values_per_session: int = Field(default=5, ge=0)
    settle_sec: float = Field(default=0.0, ge=0)


@dataclass
class NormalScenario(Scenario):
    type_name: ClassVar[str] = "normal"
    cfg: NormalConfig

    async def run(self, target: str) -> ScenarioResult:
        samples = LatencySamples()
        failures: list[str] = []

        async def one(i: int) -> None:
            station = VirtualStation(
                charge_point_id=f"{self.cfg.station_prefix}{i:05d}",
                target=target,
                protocol=self.cfg.protocol,
            )
            try:
                async with station.connected() as cp:
                    await station.boot(cp)
                    await station.status(cp, 1, ChargePointStatus.preparing)
                    txn = await station.start_transaction(cp, 1, "RFID-SIM")
                    for n in range(self.cfg.meter_values_per_session):
                        await station.meter_values(cp, 1, txn, (n + 1) * 100)
                    await station.stop_transaction(cp, txn, meter_stop=5_000)
                    await station.status(cp, 1, ChargePointStatus.available)
            except Exception as exc:
                failures.append(f"{station.charge_point_id}: {exc!r}")
                return
            samples.boot.extend(station.latency.boot)
            samples.heartbeat.extend(station.latency.heartbeat)
            samples.start_tx.extend(station.latency.start_tx)

        await asyncio.gather(*(one(i) for i in range(self.cfg.stations)))

        passed = not failures
        return ScenarioResult(
            name="normal",
            passed=passed,
            assertions=["every station completes a full session with no error"],
            failures=failures,
            latency=samples.all(),
            stats={"stations": self.cfg.stations},
        )
