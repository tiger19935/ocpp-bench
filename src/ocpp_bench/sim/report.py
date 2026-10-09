from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field


@dataclass
class LatencySummary:
    count: int
    min_sec: float
    p50_sec: float
    p95_sec: float
    p99_sec: float
    max_sec: float


def summarise(samples: list[float]) -> LatencySummary | None:
    if not samples:
        return None
    s = sorted(samples)
    return LatencySummary(
        count=len(s),
        min_sec=s[0],
        p50_sec=_percentile(s, 50),
        p95_sec=_percentile(s, 95),
        p99_sec=_percentile(s, 99),
        max_sec=s[-1],
    )


def _percentile(sorted_samples: list[float], pct: float) -> float:
    k = (pct / 100.0) * (len(sorted_samples) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_samples[int(k)]
    return sorted_samples[f] + (sorted_samples[c] - sorted_samples[f]) * (k - f)


@dataclass
class CsmsSnapshot:
    stations: int
    quarantined: int
    total_reconnects: int
    queue_drops: int


@dataclass
class Report:
    scenario: str
    passed: bool
    assertions: list[str]
    failures: list[str]
    latency: dict[str, LatencySummary]
    stats: dict[str, int | float | str]
    csms: CsmsSnapshot | None = field(default=None)

    def to_json(self) -> str:
        d = asdict(self)
        # Strip None csms for cleanliness.
        if d["csms"] is None:
            d["csms"] = {}
        return json.dumps(d, indent=2, sort_keys=True)

    def to_table(self) -> str:
        lines = [
            f"scenario:  {self.scenario}",
            f"passed:    {self.passed}",
            "assertions:",
        ]
        lines.extend(f"  - {a}" for a in self.assertions)
        if self.failures:
            lines.append("failures:")
            lines.extend(f"  - {f}" for f in self.failures)
        if self.latency:
            lines.append("latency (sec):")
            for name, s in self.latency.items():
                lines.append(
                    f"  {name:<24s} n={s.count:>6d} p50={s.p50_sec:.3f} "
                    f"p95={s.p95_sec:.3f} p99={s.p99_sec:.3f} max={s.max_sec:.3f}"
                )
        if self.stats:
            lines.append("stats:")
            for k, v in self.stats.items():
                lines.append(f"  {k}: {v}")
        if self.csms is not None:
            lines.append("csms:")
            lines.append(f"  stations:          {self.csms.stations}")
            lines.append(f"  quarantined:       {self.csms.quarantined}")
            lines.append(f"  total_reconnects:  {self.csms.total_reconnects}")
            lines.append(f"  queue_drops:       {self.csms.queue_drops}")
        return "\n".join(lines)
