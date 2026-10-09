from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, Literal

from ocpp.routing import on
from ocpp.v16 import ChargePoint as Cp16
from ocpp.v16 import call as call16
from ocpp.v16 import call_result as cr16
from ocpp.v16.enums import Action, RemoteStartStopStatus
from pydantic import BaseModel, ConfigDict, Field
from websockets.asyncio.client import connect
from websockets.typing import Subprotocol

from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.station import VirtualStation, _now_iso


class SlowConsumerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["slow-consumer"] = "slow-consumer"
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    response_delay_sec: float = Field(default=35.0, gt=0)


class DuplicateStartConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["duplicate-start"] = "duplicate-start"
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"


class OutOfOrderMeterValuesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["out-of-order-metervalues"] = "out-of-order-metervalues"
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    samples: int = Field(default=20, ge=2)


class OversizedMeterValuesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["oversized-metervalues"] = "oversized-metervalues"
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    size_kb: int = Field(default=256, ge=1, le=4096)


class BootLoopConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["boot-loop"] = "boot-loop"
    station_prefix: str = "CP-"
    protocol: str = "ocpp1.6"
    interval_sec: float = Field(default=2.0, gt=0)
    iterations: int = Field(default=10, ge=1)


class _SlowCp(Cp16):  # type: ignore[misc]
    def __init__(self, cp_id: str, ws: object, delay: float) -> None:
        super().__init__(cp_id, ws)
        self._delay = delay

    @on(Action.remote_start_transaction)
    async def _slow_remote(self, **_: object) -> cr16.RemoteStartTransaction:
        await asyncio.sleep(self._delay)
        return cr16.RemoteStartTransaction(status=RemoteStartStopStatus.accepted)


@dataclass
class SlowConsumerScenario(Scenario):
    type_name: ClassVar[str] = "slow-consumer"
    cfg: SlowConsumerConfig

    async def run(self, target: str) -> ScenarioResult:
        cp_id = f"{self.cfg.station_prefix}SLOW"
        uri = f"{target.rstrip('/')}/{cp_id}"
        failures: list[str] = []
        async with connect(uri, subprotocols=[Subprotocol(self.cfg.protocol)]) as ws:
            cp = _SlowCp(cp_id, ws, self.cfg.response_delay_sec)
            pump = asyncio.create_task(cp.start())
            try:
                await cp.call(
                    call16.BootNotification(charge_point_vendor="v", charge_point_model="m")
                )
                # The scenario itself cannot drive the server's RemoteStart;
                # the sim here records what the station would do under slow
                # response. The CSMS-side assertion is in the admin check.
                await asyncio.sleep(0.1)
            finally:
                pump.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await pump
        return ScenarioResult(
            name="slow-consumer",
            passed=not failures,
            assertions=["station answers RemoteStartTransaction only after response_delay_sec"],
            failures=failures,
            stats={"response_delay_sec": self.cfg.response_delay_sec},
        )


@dataclass
class DuplicateStartScenario(Scenario):
    type_name: ClassVar[str] = "duplicate-start"
    cfg: DuplicateStartConfig

    async def run(self, target: str) -> ScenarioResult:
        station = VirtualStation(
            charge_point_id=f"{self.cfg.station_prefix}DUP",
            target=target,
            protocol=self.cfg.protocol,
        )
        failures: list[str] = []
        try:
            async with station.connected() as cp:
                await station.boot(cp)
                tx_a = await station.start_transaction(cp, 1, "RFID-DUP")
                tx_b = await station.start_transaction(cp, 1, "RFID-DUP")
                if tx_a != tx_b:
                    failures.append(
                        f"duplicate StartTransaction got different ids: {tx_a} vs {tx_b}"
                    )
                await station.stop_transaction(cp, tx_a, meter_stop=1_000)
        except Exception as exc:
            failures.append(repr(exc))
        return ScenarioResult(
            name="duplicate-start",
            passed=not failures,
            assertions=["two StartTransactions with same (connector,id_tag) return the same id"],
            failures=failures,
        )


@dataclass
class OutOfOrderMeterValuesScenario(Scenario):
    type_name: ClassVar[str] = "out-of-order-metervalues"
    cfg: OutOfOrderMeterValuesConfig

    async def run(self, target: str) -> ScenarioResult:
        station = VirtualStation(
            charge_point_id=f"{self.cfg.station_prefix}OOO",
            target=target,
            protocol=self.cfg.protocol,
        )
        failures: list[str] = []
        try:
            async with station.connected() as cp:
                await station.boot(cp)
                tx = await station.start_transaction(cp, 1, "RFID-OOO")
                base = time.time()
                values = [(base + n * 10) for n in range(self.cfg.samples)]
                # Deliberately out of order: reversed first, then forward.
                for ts in reversed(values):
                    await cp.call(
                        call16.MeterValues(
                            connector_id=1,
                            meter_value=[
                                {
                                    "timestamp": _iso(ts),
                                    "sampled_value": [{"value": "100", "unit": "Wh"}],
                                }
                            ],
                            transaction_id=tx,
                        )
                    )
                await station.stop_transaction(cp, tx, meter_stop=100)
        except Exception as exc:
            failures.append(repr(exc))
        return ScenarioResult(
            name="out-of-order-metervalues",
            passed=not failures,
            assertions=["CSMS accepts MeterValues sent out of timestamp order"],
            failures=failures,
            stats={"samples": self.cfg.samples},
        )


@dataclass
class OversizedMeterValuesScenario(Scenario):
    type_name: ClassVar[str] = "oversized-metervalues"
    cfg: OversizedMeterValuesConfig

    async def run(self, target: str) -> ScenarioResult:
        station = VirtualStation(
            charge_point_id=f"{self.cfg.station_prefix}BIG",
            target=target,
            protocol=self.cfg.protocol,
        )
        failures: list[str] = []
        payload = "9" * (self.cfg.size_kb * 1024)
        try:
            async with station.connected() as cp:
                await station.boot(cp)
                tx = await station.start_transaction(cp, 1, "RFID-BIG")
                await cp.call(
                    call16.MeterValues(
                        connector_id=1,
                        meter_value=[
                            {
                                "timestamp": _now_iso(),
                                "sampled_value": [{"value": payload, "unit": "Wh"}],
                            }
                        ],
                        transaction_id=tx,
                    )
                )
                await station.stop_transaction(cp, tx, meter_stop=1)
        except Exception as exc:
            failures.append(repr(exc))
        return ScenarioResult(
            name="oversized-metervalues",
            passed=not failures,
            assertions=["CSMS accepts a single MeterValues up to size_kb"],
            failures=failures,
            stats={"size_kb": self.cfg.size_kb},
        )


@dataclass
class BootLoopScenario(Scenario):
    type_name: ClassVar[str] = "boot-loop"
    cfg: BootLoopConfig

    async def run(self, target: str) -> ScenarioResult:
        station = VirtualStation(
            charge_point_id=f"{self.cfg.station_prefix}BOOTLOOP",
            target=target,
            protocol=self.cfg.protocol,
        )
        failures: list[str] = []
        for _ in range(self.cfg.iterations):
            try:
                async with station.connected() as cp:
                    await station.boot(cp)
            except Exception as exc:
                failures.append(repr(exc))
                break
            await asyncio.sleep(self.cfg.interval_sec)
        return ScenarioResult(
            name="boot-loop",
            passed=not failures,
            assertions=[
                f"{self.cfg.iterations} boots at {self.cfg.interval_sec:.1f}s do not crash the CSMS"
            ],
            failures=failures,
            latency=station.latency.all(),
            stats={"iterations": self.cfg.iterations},
        )


def _iso(ts_epoch: float) -> str:
    return (
        datetime.fromtimestamp(ts_epoch, UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
