from __future__ import annotations

from typing import Annotated

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
from ocpp_bench.sim.scenarios.flapping import FlappingConfig, FlappingScenario
from ocpp_bench.sim.scenarios.normal import NormalConfig, NormalScenario
from ocpp_bench.sim.scenarios.reconnect_storm import (
    ReconnectStormConfig,
    ReconnectStormScenario,
)
from ocpp_bench.sim.scenarios.soak import SoakConfig, SoakScenario

ScenarioConfig = Annotated[
    NormalConfig
    | SoakConfig
    | ReconnectStormConfig
    | FlappingConfig
    | SlowConsumerConfig
    | DuplicateStartConfig
    | OutOfOrderMeterValuesConfig
    | OversizedMeterValuesConfig
    | BootLoopConfig,
    Field(discriminator="type"),
]
_ADAPTER: TypeAdapter[
    NormalConfig
    | SoakConfig
    | ReconnectStormConfig
    | FlappingConfig
    | SlowConsumerConfig
    | DuplicateStartConfig
    | OutOfOrderMeterValuesConfig
    | OversizedMeterValuesConfig
    | BootLoopConfig
] = TypeAdapter(ScenarioConfig)  # type: ignore[arg-type, unused-ignore]


_SCENARIO_BY_CONFIG: dict[type, type[Scenario]] = {
    NormalConfig: NormalScenario,
    SoakConfig: SoakScenario,
    ReconnectStormConfig: ReconnectStormScenario,
    FlappingConfig: FlappingScenario,
    SlowConsumerConfig: SlowConsumerScenario,
    DuplicateStartConfig: DuplicateStartScenario,
    OutOfOrderMeterValuesConfig: OutOfOrderMeterValuesScenario,
    OversizedMeterValuesConfig: OversizedMeterValuesScenario,
    BootLoopConfig: BootLoopScenario,
}


def load_scenario(data: dict[str, object]) -> Scenario:
    cfg = _ADAPTER.validate_python(data)
    return _SCENARIO_BY_CONFIG[type(cfg)](cfg=cfg)  # type: ignore[call-arg]


__all__ = [
    "BootLoopConfig",
    "BootLoopScenario",
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
