from __future__ import annotations

from typing import Annotated

from pydantic import Field, TypeAdapter

from ocpp_bench.sim.scenarios.base import Scenario, ScenarioResult
from ocpp_bench.sim.scenarios.normal import NormalConfig, NormalScenario
from ocpp_bench.sim.scenarios.soak import SoakConfig, SoakScenario

ScenarioConfig = Annotated[NormalConfig | SoakConfig, Field(discriminator="type")]
_ADAPTER: TypeAdapter[NormalConfig | SoakConfig] = TypeAdapter(ScenarioConfig)  # type: ignore[arg-type]


def load_scenario(data: dict[str, object]) -> Scenario:
    cfg = _ADAPTER.validate_python(data)
    if isinstance(cfg, NormalConfig):
        return NormalScenario(cfg=cfg)
    return SoakScenario(cfg=cfg)


__all__ = [
    "NormalConfig",
    "NormalScenario",
    "Scenario",
    "ScenarioConfig",
    "ScenarioResult",
    "SoakConfig",
    "SoakScenario",
    "load_scenario",
]
