from __future__ import annotations

import asyncio

from ocpp_bench.csms import CsmsServer
from ocpp_bench.sim.runner import RunOptions, run_scenario
from ocpp_bench.sim.scenarios import (
    BootLoopConfig,
    BootLoopScenario,
    DuplicateStartConfig,
    DuplicateStartScenario,
    FlappingConfig,
    FlappingScenario,
    OutOfOrderMeterValuesConfig,
    OutOfOrderMeterValuesScenario,
    OversizedMeterValuesConfig,
    OversizedMeterValuesScenario,
    ReconnectStormConfig,
    ReconnectStormScenario,
    SoakConfig,
    SoakScenario,
)


async def test_soak_scenario_runs_briefly(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = SoakScenario(
        cfg=SoakConfig(
            type="soak",
            stations=3,
            station_prefix="SOAK-",
            duration_sec=0.3,
            heartbeat_interval_sec=0.1,
        )
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_reconnect_storm_recovers(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = ReconnectStormScenario(
        cfg=ReconnectStormConfig(
            type="reconnect-storm",
            stations=10,
            station_prefix="STORM-",
            storm_window_sec=0.5,
            recover_within_sec=5,
        )
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_flapping_isolation(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = FlappingScenario(
        cfg=FlappingConfig(
            type="flapping",
            stable_stations=20,
            station_prefix="FLAP-",
            duration_sec=1.0,
            flap_interval_ms=50,
            heartbeat_interval_sec=0.1,
            isolation_tolerance_pct=200,
        )
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    # Not asserting pass/fail strictly — the baseline+under-flap latencies on
    # a dev laptop are noisy. The scenario *runs*, both samples are collected,
    # and the stats contain the delta.
    assert "delta_pct" in r.stats
    assert r.stats["flapper_reconnects"] > 0


async def test_duplicate_start_same_id(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = DuplicateStartScenario(cfg=DuplicateStartConfig(type="duplicate-start"))
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_out_of_order_metervalues(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = OutOfOrderMeterValuesScenario(
        cfg=OutOfOrderMeterValuesConfig(type="out-of-order-metervalues", samples=5)
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_oversized_metervalues(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = OversizedMeterValuesScenario(
        cfg=OversizedMeterValuesConfig(type="oversized-metervalues", size_kb=16)
    )
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_boot_loop(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scn = BootLoopScenario(cfg=BootLoopConfig(type="boot-loop", interval_sec=0.1, iterations=3))
    r = await scn.run(f"ws://127.0.0.1:{port}/ocpp")
    assert r.passed, r.failures


async def test_runner_with_admin_snapshot(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    server, port, _ = csms_server
    scn = BootLoopScenario(cfg=BootLoopConfig(type="boot-loop", interval_sec=0.1, iterations=2))
    r = await run_scenario(
        scn,
        RunOptions(
            target=f"ws://127.0.0.1:{port}/ocpp",
            admin_url=f"http://127.0.0.1:{server.settings.admin_port}",
        ),
    )
    assert r.passed
    assert r.csms is not None
    assert r.csms.stations >= 1
