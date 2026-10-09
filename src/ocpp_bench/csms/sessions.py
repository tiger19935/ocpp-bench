from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field


@dataclass
class ActiveTransaction:
    transaction_id: int
    charge_point_id: str
    connector_id: int
    id_tag: str
    meter_start: int
    opened_at: float


@dataclass
class SessionStore:
    duplicate_window_sec: float = 10.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _ids: itertools.count[int] = field(default_factory=lambda: itertools.count(1))
    _active: dict[tuple[str, int], ActiveTransaction] = field(default_factory=dict)
    _by_id: dict[int, ActiveTransaction] = field(default_factory=dict)

    async def open_or_dedupe(
        self,
        charge_point_id: str,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        now: float,
    ) -> tuple[ActiveTransaction, bool]:
        async with self._lock:
            existing = self._active.get((charge_point_id, connector_id))
            if (
                existing is not None
                and existing.id_tag == id_tag
                and (now - existing.opened_at) <= self.duplicate_window_sec
            ):
                return existing, True

            txn = ActiveTransaction(
                transaction_id=next(self._ids),
                charge_point_id=charge_point_id,
                connector_id=connector_id,
                id_tag=id_tag,
                meter_start=meter_start,
                opened_at=now,
            )
            self._active[(charge_point_id, connector_id)] = txn
            self._by_id[txn.transaction_id] = txn
            return txn, False

    async def open(
        self,
        charge_point_id: str,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        now: float,
    ) -> ActiveTransaction:
        txn, _ = await self.open_or_dedupe(
            charge_point_id=charge_point_id,
            connector_id=connector_id,
            id_tag=id_tag,
            meter_start=meter_start,
            now=now,
        )
        return txn

    async def close(self, transaction_id: int) -> ActiveTransaction | None:
        async with self._lock:
            txn = self._by_id.pop(transaction_id, None)
            if txn is not None:
                self._active.pop((txn.charge_point_id, txn.connector_id), None)
            return txn

    async def get(self, transaction_id: int) -> ActiveTransaction | None:
        async with self._lock:
            return self._by_id.get(transaction_id)

    async def active_for(self, charge_point_id: str, connector_id: int) -> ActiveTransaction | None:
        async with self._lock:
            return self._active.get((charge_point_id, connector_id))
