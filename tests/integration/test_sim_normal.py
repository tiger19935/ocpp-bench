from __future__ import annotations

import asyncio

from ocpp_bench.csms import CsmsServer
from ocpp_bench.sim.scenarios import NormalConfig, NormalScenario


async def test_normal_scenario_passes_against_in_process_csms(
    csms_server: tuple[CsmsServer, int, asyncio.Task[None]],
) -> None:
    _, port, _ = csms_server
    scenario = NormalScenario(
        cfg=NormalConfig(
            type="normal",
            stations=5,
            station_prefix="NORMAL-SIM-",
            meter_values_per_session=2,
        )
    )
    result = await scenario.run(f"ws://127.0.0.1:{port}/ocpp")
    assert result.passed, result.failures
    assert len(result.latency["boot"]) == 5
    assert len(result.latency["start_tx"]) == 5
