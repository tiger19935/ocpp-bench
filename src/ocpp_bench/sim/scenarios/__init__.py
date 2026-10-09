from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter

from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.scenarios.flapping import FlappingConfig, FlappingScenario
from ocpp_bench.sim.scenarios.normal import NormalConfig, NormalScenario
from ocpp_bench.sim.scenarios.reconnect_storm import (
    ReconnectStormConfig,
    ReconnectStormScenario,
)
from ocpp_bench.sim.scenarios.soak import SoakConfig, SoakScenario

ScenarioConfig = Annotated[
    NormalConfig | SoakConfig | ReconnectStormConfig | FlappingConfig,
    Field(discriminator="type"),
]
_ADAPTER: TypeAdapter[NormalConfig | SoakConfig | ReconnectStormConfig | FlappingConfig] = (
    TypeAdapter(ScenarioConfig)  # type: ignore[arg-type]
)


def load_scenario(data: dict[str, object]) -> Scenario:
    cfg = _ADAPTER.validate_python(data)
    if isinstance(cfg, NormalConfig):
        return NormalScenario(cfg=cfg)
    if isinstance(cfg, SoakConfig):
        return SoakScenario(cfg=cfg)
    if isinstance(cfg, ReconnectStormConfig):
        return ReconnectStormScenario(cfg=cfg)
    return FlappingScenario(cfg=cfg)


__all__ = [
    "FlappingConfig",
    "FlappingScenario",
    "NormalConfig",
    "NormalScenario",
    "ReconnectStormConfig",
    "ReconnectStormScenario",
    "Scenario",
    "ScenarioConfig",
    "ScenarioResult",
    "SoakConfig",
    "SoakScenario",
    "load_scenario",
]
