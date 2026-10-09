from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import LatencySamples, VirtualStation


class FlappingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["flapping"] = "flapping"
    stable_stations: int = Field(default=199, ge=1, le=10_000)
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    duration_sec: float = Field(default=10.0, gt=0)
    flap_interval_ms: int = Field(default=100, ge=10)
    heartbeat_interval_sec: float = Field(default=1.0, gt=0)
    isolation_tolerance_pct: float = Field(default=20.0, ge=0)


@dataclass
class FlappingScenario(Scenario):
    type_name: ClassVar[str] = "flapping"
    cfg: FlappingConfig

    async def run(self, target: str) -> ScenarioResult:
        baseline = LatencySamples()
        warm_task = asyncio.create_task(
            _run_stable(self.cfg, target, baseline, self.cfg.duration_sec, under_flap=False)
        )
        await warm_task
        baseline_hb_p95 = _p95(baseline.heartbeat)

        # Now the real run with the flapper misbehaving in parallel.
        under = LatencySamples()
        flapper_reconnects = 0

        async def flap() -> int:
            nonlocal flapper_reconnects
            fs = VirtualStation(
                charge_point_id=f"{self.cfg.station_prefix}FLAPPER",
                target=target,
                protocol=self.cfg.protocol,
            )
            deadline = time.monotonic() + self.cfg.duration_sec
            while time.monotonic() < deadline:
                flapper_reconnects += 1
                with contextlib.suppress(Exception):
                    async with fs.connected() as cp:
                        await fs.boot(cp)
                        await asyncio.sleep(self.cfg.flap_interval_ms / 1000)
                await asyncio.sleep(self.cfg.flap_interval_ms / 1000)
            return flapper_reconnects

        flapper = asyncio.create_task(flap())
        stable = asyncio.create_task(
            _run_stable(self.cfg, target, under, self.cfg.duration_sec, under_flap=True)
        )
        await asyncio.gather(flapper, stable)
        under_hb_p95 = _p95(under.heartbeat)

        delta_pct = (
            100.0 * (under_hb_p95 - baseline_hb_p95) / baseline_hb_p95
            if baseline_hb_p95 > 0
            else 0.0
        )
        passed = delta_pct <= self.cfg.isolation_tolerance_pct
        return ScenarioResult(
            name="flapping",
            passed=passed,
            assertions=[
                f"heartbeat p95 of stable stations rises by no more than "
                f"{self.cfg.isolation_tolerance_pct:.0f}% while one station flaps"
            ],
            failures=(
                []
                if passed
                else [
                    f"heartbeat p95 rose from {baseline_hb_p95:.3f}s to "
                    f"{under_hb_p95:.3f}s ({delta_pct:.1f}%)"
                ]
            ),
            latency={
                "baseline_heartbeat": baseline.heartbeat,
                "under_flap_heartbeat": under.heartbeat,
            },
            stats={
                "stable_stations": self.cfg.stable_stations,
                "flapper_reconnects": flapper_reconnects,
                "baseline_hb_p95_sec": baseline_hb_p95,
                "under_flap_hb_p95_sec": under_hb_p95,
                "delta_pct": delta_pct,
            },
        )


async def _run_stable(
    cfg: FlappingConfig,
    target: str,
    samples: LatencySamples,
    duration_sec: float,
    under_flap: bool,
) -> None:
    del under_flap

    async def one(i: int) -> None:
        station = VirtualStation(
            charge_point_id=f"{cfg.station_prefix}STABLE-{i:05d}",
            target=target,
            protocol=cfg.protocol,
        )
        try:
            async with station.connected() as cp:
                await station.boot(cp)
                deadline = time.monotonic() + duration_sec
                while time.monotonic() < deadline:
                    await station.heartbeat(cp)
                    await asyncio.sleep(cfg.heartbeat_interval_sec)
        except Exception:
            return
        samples.heartbeat.extend(station.latency.heartbeat)

    await asyncio.gather(*(one(i) for i in range(cfg.stable_stations)))


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, round(0.95 * (len(s) - 1)))
    return s[idx]
