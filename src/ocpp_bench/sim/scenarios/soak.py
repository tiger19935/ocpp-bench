from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocpp_bench.logging import get_logger
from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import LatencySamples, VirtualStation

logger = get_logger("sim.scenarios.soak")


class SoakConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["soak"] = "soak"
    stations: int = Field(ge=1, le=10_000)
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    duration_sec: float = Field(default=60.0, gt=0)
    heartbeat_interval_sec: float = Field(default=10.0, gt=0)


@dataclass
class SoakScenario(Scenario):
    type_name: ClassVar[str] = "soak"
    cfg: SoakConfig

    async def run(self, target: str) -> ScenarioResult:
        samples = LatencySamples()
        failures: list[str] = []
        deadline = time.monotonic() + self.cfg.duration_sec

        async def one(i: int) -> None:
            station = VirtualStation(
                charge_point_id=f"{self.cfg.station_prefix}{i:05d}",
                target=target,
                protocol=self.cfg.protocol,
            )
            try:
                async with station.connected() as cp:
                    await station.boot(cp)
                    while time.monotonic() < deadline:
                        await station.heartbeat(cp)
                        await asyncio.sleep(self.cfg.heartbeat_interval_sec)
            except Exception as exc:
                failures.append(f"{station.charge_point_id}: {exc!r}")
                return
            samples.boot.extend(station.latency.boot)
            samples.heartbeat.extend(station.latency.heartbeat)

        tasks = [asyncio.create_task(one(i)) for i in range(self.cfg.stations)]
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await t

        return ScenarioResult(
            name="soak",
            passed=not failures,
            assertions=[f"every station heartbeats for {self.cfg.duration_sec:.0f}s"],
            failures=failures,
            latency=samples.all(),
            stats={
                "stations": self.cfg.stations,
                "duration_sec": self.cfg.duration_sec,
            },
        )
