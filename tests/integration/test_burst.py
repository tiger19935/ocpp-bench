from __future__ import annotations

import asyncio

from ocpp_bench.csms import CsmsServer
from ocpp_bench.sim.scenarios import BurstConfig, BurstScenario


async def test_burst_small_passes(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    scn = BurstScenario(
        cfg=BurstConfig(
            type="burst",
            stations=100,
            station_prefix="BURST-",
            duration_sec=5.0,
            heartbeat_interval_sec=1.0,
            metervalue_interval_sec=2.0,
            p95_budget_sec=1.5,
        )
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures
    assert r.stats["stations_finished_connected"] == 100
    assert r.stats["callerror_count"] == 0
    station = await server.store.get("BURST-00000")
    assert station is not None
    assert station.queue_drops == 0
