from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, cast

from pydantic import Field, TypeAdapter

from ocpp_bench.sim.scenarios.adversarial import (
    BootLoopConfig,
    BootLoopScenario,
    DuplicateStartConfig,
    DuplicateStartScenario,
    OutOfOrderMeterValuesConfig,
    OutOfOrderMeterValuesScenario,
    OversizedMeterValuesConfig,
    OversizedMeterValuesScenario,
    SlowConsumerConfig,
    SlowConsumerScenario,
)
from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.scenarios.burst import BurstConfig, BurstScenario
from ocpp_bench.sim.scenarios.flapping import FlappingConfig, FlappingScenario
from ocpp_bench.sim.scenarios.normal import NormalConfig, NormalScenario
from ocpp_bench.sim.scenarios.reconnect_storm import (
    ReconnectStormConfig,
    ReconnectStormScenario,
)
from ocpp_bench.sim.scenarios.soak import SoakConfig, SoakScenario

_AnyConfig = (
    NormalConfig
    | SoakConfig
    | ReconnectStormConfig
    | FlappingConfig
    | SlowConsumerConfig
    | DuplicateStartConfig
    | OutOfOrderMeterValuesConfig
    | OversizedMeterValuesConfig
    | BootLoopConfig
    | BurstConfig
)
ScenarioConfig = Annotated[_AnyConfig, Field(discriminator="type")]
# TypeAdapter accepts Annotated[Union, Field(discriminator=...)] at runtime,
# but mypy's TypeAdapter[T] overload only accepts a plain type[T]. The ignore
# documents a known pydantic / mypy mismatch; the unused-ignore pair keeps it
# valid under both macOS and Linux mypy (Linux stops reporting the arg-type).
_ADAPTER: TypeAdapter[_AnyConfig] = TypeAdapter(ScenarioConfig)  # type: ignore[arg-type, unused-ignore]


_FACTORIES: dict[type[_AnyConfig], Callable[[_AnyConfig], Scenario]] = {
    NormalConfig: lambda c: NormalScenario(cfg=cast(NormalConfig, c)),
    SoakConfig: lambda c: SoakScenario(cfg=cast(SoakConfig, c)),
    ReconnectStormConfig: lambda c: ReconnectStormScenario(cfg=cast(ReconnectStormConfig, c)),
    FlappingConfig: lambda c: FlappingScenario(cfg=cast(FlappingConfig, c)),
    SlowConsumerConfig: lambda c: SlowConsumerScenario(cfg=cast(SlowConsumerConfig, c)),
    DuplicateStartConfig: lambda c: DuplicateStartScenario(cfg=cast(DuplicateStartConfig, c)),
    OutOfOrderMeterValuesConfig: lambda c: OutOfOrderMeterValuesScenario(
        cfg=cast(OutOfOrderMeterValuesConfig, c)
    ),
    OversizedMeterValuesConfig: lambda c: OversizedMeterValuesScenario(
        cfg=cast(OversizedMeterValuesConfig, c)
    ),
    BootLoopConfig: lambda c: BootLoopScenario(cfg=cast(BootLoopConfig, c)),
    BurstConfig: lambda c: BurstScenario(cfg=cast(BurstConfig, c)),
}


def load_scenario(data: dict[str, object]) -> Scenario:
    cfg = _ADAPTER.validate_python(data)
    return _FACTORIES[type(cfg)](cfg)


__all__ = [
    "BootLoopConfig",
    "BootLoopScenario",
    "BurstConfig",
    "BurstScenario",
    "DuplicateStartConfig",
    "DuplicateStartScenario",
    "FlappingConfig",
    "FlappingScenario",
    "NormalConfig",
    "NormalScenario",
    "OutOfOrderMeterValuesConfig",
    "OutOfOrderMeterValuesScenario",
    "OversizedMeterValuesConfig",
    "OversizedMeterValuesScenario",
    "ReconnectStormConfig",
    "ReconnectStormScenario",
    "Scenario",
    "ScenarioConfig",
    "ScenarioResult",
    "SlowConsumerConfig",
    "SlowConsumerScenario",
    "SoakConfig",
    "SoakScenario",
    "load_scenario",
]
