from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from typing import ClassVar, Literal

from ocpp.v16 import call as call16
from ocpp.v16.enums import ChargePointStatus
from pydantic import BaseModel, ConfigDict, Field

from ocpp_bench.logging import get_logger
from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import LatencySamples, VirtualStation, _now_iso

logger = get_logger("sim.scenarios.burst")


class BurstConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["burst"] = "burst"
    stations: int = Field(ge=1, le=10_000)
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    duration_sec: float = Field(default=60.0, gt=0)
    heartbeat_interval_sec: float = Field(default=1.0, gt=0)
    metervalue_interval_sec: float = Field(default=2.0, gt=0)
    p95_budget_sec: float = Field(default=0.5, gt=0)


@dataclass
class _Agg:
    samples: LatencySamples
    mv_latency: list[float]
    failures: list[str]
    callerrors: int
    finished: int
    lock: asyncio.Lock


async def _send_metervalue(cp: object, txn: int) -> None:
    await cp.call(  # type: ignore[attr-defined]
        call16.MeterValues(
            connector_id=1,
            meter_value=[
                {
                    "timestamp": _now_iso(),
                    "sampled_value": [
                        {
                            "value": "1000",
                            "measurand": "Energy.Active.Import.Register",
                            "unit": "Wh",
                        }
                    ],
                }
            ],
            transaction_id=txn,
        )
    )


async def _run_one(cfg: BurstConfig, target: str, i: int, agg: _Agg) -> None:
    station = VirtualStation(
        charge_point_id=f"{cfg.station_prefix}{i:05d}",
        target=target,
        protocol=cfg.protocol,
    )
    try:
        async with station.connected() as cp:
            await station.boot(cp)
            await station.status(cp, 1, ChargePointStatus.preparing)
            txn = await station.start_transaction(cp, 1, f"RFID-{i:05d}")
            await station.status(cp, 1, ChargePointStatus.charging)

            deadline = time.monotonic() + cfg.duration_sec
            last_mv = time.monotonic()
            while time.monotonic() < deadline:
                await station.heartbeat(cp)
                if time.monotonic() - last_mv >= cfg.metervalue_interval_sec:
                    t0 = time.monotonic()
                    try:
                        await _send_metervalue(cp, txn)
                    except Exception as exc:
                        if "CallError" in repr(exc) or "InternalError" in repr(exc):
                            async with agg.lock:
                                agg.callerrors += 1
                        raise
                    agg.mv_latency.append(time.monotonic() - t0)
                    last_mv = time.monotonic()
                await asyncio.sleep(cfg.heartbeat_interval_sec)

            await station.stop_transaction(cp, txn, meter_stop=10_000)
            async with agg.lock:
                agg.finished += 1
    except Exception as exc:
        async with agg.lock:
            agg.failures.append(f"{station.charge_point_id}: {exc!r}")
        return
    agg.samples.heartbeat.extend(station.latency.heartbeat)
    agg.samples.start_tx.extend(station.latency.start_tx)
    agg.samples.boot.extend(station.latency.boot)


@dataclass
class BurstScenario(Scenario):
    type_name: ClassVar[str] = "burst"
    cfg: BurstConfig

    async def run(self, target: str) -> ScenarioResult:
        agg = _Agg(
            samples=LatencySamples(),
            mv_latency=[],
            failures=[],
            callerrors=0,
            finished=0,
            lock=asyncio.Lock(),
        )
        tasks = [
            asyncio.create_task(_run_one(self.cfg, target, i, agg))
            for i in range(self.cfg.stations)
        ]
        try:
            await asyncio.gather(*tasks)
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await t

        hb_p95 = _p95(agg.samples.heartbeat)
        mv_p95 = _p95(agg.mv_latency)
        failures = list(agg.failures)
        if agg.callerrors:
            failures.append(f"{agg.callerrors} CALLERROR responses from CSMS")
        if hb_p95 > self.cfg.p95_budget_sec:
            failures.append(
                f"heartbeat p95 {hb_p95:.3f}s exceeds budget {self.cfg.p95_budget_sec:.3f}s"
            )
        if agg.finished < self.cfg.stations:
            failures.append(f"only {agg.finished}/{self.cfg.stations} stations finished connected")

        return ScenarioResult(
            name="burst",
            passed=not failures,
            assertions=[
                "every station finishes the window still connected",
                "no CALLERROR responses from the CSMS",
                f"heartbeat p95 <= {self.cfg.p95_budget_sec:.3f}s",
            ],
            failures=failures,
            latency={"heartbeat": agg.samples.heartbeat, "metervalues": agg.mv_latency},
            stats={
                "stations": self.cfg.stations,
                "duration_sec": self.cfg.duration_sec,
                "heartbeat_p95_sec": hb_p95,
                "metervalues_p95_sec": mv_p95,
                "stations_finished_connected": agg.finished,
                "callerror_count": agg.callerrors,
                "msg_per_sec_target": self.cfg.stations
                * (1 / self.cfg.heartbeat_interval_sec + 1 / self.cfg.metervalue_interval_sec),
            },
        )


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[max(0, round(0.95 * (len(s) - 1)))]
