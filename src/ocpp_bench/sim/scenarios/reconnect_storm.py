from __future__ import annotations

import asyncio
import contextlib
import random
import time
from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import LatencySamples, VirtualStation


class ReconnectStormConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["reconnect-storm"] = "reconnect-storm"
    stations: int = Field(ge=1, le=10_000)
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    storm_window_sec: float = Field(default=2.0, gt=0)
    recover_within_sec: float = Field(default=10.0, gt=0)


@dataclass
class ReconnectStormScenario(Scenario):
    type_name: ClassVar[str] = "reconnect-storm"
    cfg: ReconnectStormConfig

    async def run(self, target: str) -> ScenarioResult:
        samples = LatencySamples()
        failures: list[str] = []
        rng = random.Random(42)

        async def life(i: int) -> None:
            station = VirtualStation(
                charge_point_id=f"{self.cfg.station_prefix}{i:05d}",
                target=target,
                protocol=self.cfg.protocol,
            )
            # First connection: boot and hold.
            try:
                async with station.connected() as cp:
                    await station.boot(cp)
            except Exception as exc:
                failures.append(f"{station.charge_point_id} first boot: {exc!r}")
                return

            # Drop + reconnect within the storm window.
            await asyncio.sleep(rng.random() * self.cfg.storm_window_sec)
            started = time.monotonic()
            try:
                async with station.connected() as cp:
                    await station.boot(cp)
                    await station.heartbeat(cp)
            except Exception as exc:
                failures.append(f"{station.charge_point_id} reconnect: {exc!r}")
                return
            samples.boot.extend(station.latency.boot)
            samples.heartbeat.extend(station.latency.heartbeat)
            if time.monotonic() - started > self.cfg.recover_within_sec:
                failures.append(
                    f"{station.charge_point_id} did not recover within "
                    f"{self.cfg.recover_within_sec:.1f}s"
                )

        tasks = [asyncio.create_task(life(i)) for i in range(self.cfg.stations)]
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await t

        return ScenarioResult(
            name="reconnect-storm",
            passed=not failures,
            assertions=[
                f"every station reconnects and heartbeats within {self.cfg.recover_within_sec:.1f}s"
            ],
            failures=failures,
            latency=samples.all(),
            stats={
                "stations": self.cfg.stations,
                "storm_window_sec": self.cfg.storm_window_sec,
            },
        )
