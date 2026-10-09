from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from ocpp_bench.protocol import StationFSM


@dataclass
class Station:
    charge_point_id: str
    protocol: str  # "ocpp1.6" | "ocpp2.0.1"
    fsm: StationFSM = field(default_factory=StationFSM)
    reconnects: int = 0
    quarantined: bool = False


class StationStore(Protocol):
    async def upsert(self, cp_id: str, protocol: str) -> Station: ...
    async def get(self, cp_id: str) -> Station | None: ...
    def iter_stations(self) -> AsyncIterator[Station]: ...


class InMemoryStationStore:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._stations: dict[str, Station] = {}

    async def upsert(self, cp_id: str, protocol: str) -> Station:
        async with self._lock:
            s = self._stations.get(cp_id)
            if s is None:
                s = Station(charge_point_id=cp_id, protocol=protocol)
                self._stations[cp_id] = s
            else:
                s.protocol = protocol
                s.reconnects += 1
            return s

    async def get(self, cp_id: str) -> Station | None:
        async with self._lock:
            return self._stations.get(cp_id)

    async def iter_stations(self) -> AsyncIterator[Station]:
        async with self._lock:
            items = list(self._stations.values())
        for s in items:
            yield s
