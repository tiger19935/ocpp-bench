from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class FlapDetector:
    window_sec: float
    limit: int
    _events: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def record(self, charge_point_id: str, now: float) -> int:
        events = self._events[charge_point_id]
        events.append(now)
        self._evict(events, now)
        return len(events)

    def rate(self, charge_point_id: str, now: float) -> int:
        events = self._events.get(charge_point_id)
        if events is None:
            return 0
        self._evict(events, now)
        return len(events)

    def is_flapping(self, charge_point_id: str, now: float) -> bool:
        return self.rate(charge_point_id, now) > self.limit

    def reset(self, charge_point_id: str) -> None:
        self._events.pop(charge_point_id, None)

    def _evict(self, events: deque[float], now: float) -> None:
        cutoff = now - self.window_sec
        while events and events[0] < cutoff:
            events.popleft()
