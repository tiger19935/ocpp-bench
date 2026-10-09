from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from ocpp_bench.sim.report import CsmsSnapshot, Report, summarise
from ocpp_bench.sim.scenarios import Scenario


@dataclass
class RunOptions:
    target: str
    admin_url: str | None  # e.g. "http://127.0.0.1:9100". None = do not assert.


async def run_scenario(scenario: Scenario, opts: RunOptions) -> Report:
    result = await scenario.run(opts.target)
    latency = {name: s for name, raw in result.latency.items() if (s := summarise(raw)) is not None}
    csms = await _snapshot(opts.admin_url) if opts.admin_url else None
    return Report(
        scenario=result.name,
        passed=result.passed,
        assertions=result.assertions,
        failures=result.failures,
        latency=latency,
        stats=result.stats,
        csms=csms,
    )


async def _snapshot(admin_url: str) -> CsmsSnapshot | None:
    url = f"{admin_url.rstrip('/')}/stations"
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as http, http.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return None
    stations = data.get("stations", [])
    return CsmsSnapshot(
        stations=len(stations),
        quarantined=sum(1 for s in stations if s.get("quarantined")),
        total_reconnects=sum(int(s.get("reconnects", 0)) for s in stations),
        queue_drops=sum(int(s.get("queue_drops", 0)) for s in stations),
    )
