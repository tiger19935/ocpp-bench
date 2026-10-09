from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

# Exponential backoff: doubles on every re-flap, capped at 60s.
# Index 0 == first offence.
_BACKOFF_SCHEDULE: Final[tuple[float, ...]] = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)


@dataclass
class _State:
    offence_index: int = 0
    last_applied_at: float = 0.0
    cleared_at: float | None = None


@dataclass
class Quarantine:
    clear_after_sec: float = 300.0
    _state: dict[str, _State] = field(default_factory=dict)

    def apply(self, charge_point_id: str, now: float) -> float:
        s = self._state.setdefault(charge_point_id, _State())
        wait = _BACKOFF_SCHEDULE[min(s.offence_index, len(_BACKOFF_SCHEDULE) - 1)]
        s.offence_index = min(s.offence_index + 1, len(_BACKOFF_SCHEDULE))
        s.last_applied_at = now
        s.cleared_at = None
        return wait

    def is_quarantined(self, charge_point_id: str) -> bool:
        s = self._state.get(charge_point_id)
        return s is not None and s.cleared_at is None

    def tick(self, charge_point_id: str, now: float) -> bool:
        """Called periodically. If stability window elapsed, clear and return True."""
        s = self._state.get(charge_point_id)
        if s is None or s.cleared_at is not None:
            return False
        if now - s.last_applied_at >= self.clear_after_sec:
            s.cleared_at = now
            s.offence_index = 0
            return True
        return False

    def reset(self, charge_point_id: str) -> None:
        self._state.pop(charge_point_id, None)

    @staticmethod
    def schedule() -> tuple[float, ...]:
        return _BACKOFF_SCHEDULE
