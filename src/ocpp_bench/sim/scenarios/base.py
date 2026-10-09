from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    assertions: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    latency: dict[str, list[float]] = field(default_factory=dict)
    stats: dict[str, int | float | str] = field(default_factory=dict)


class Scenario(ABC):
    type_name: ClassVar[str] = "base"

    @abstractmethod
    async def run(self, target: str) -> ScenarioResult: ...
