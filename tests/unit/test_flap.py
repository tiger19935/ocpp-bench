from __future__ import annotations

from ocpp_bench.health import FlapDetector


def test_counts_only_within_window() -> None:
    f = FlapDetector(window_sec=10.0, limit=3)
    for ts in [0.0, 1.0, 2.0, 3.0]:
        f.record("CP-1", ts)
    assert f.rate("CP-1", 3.0) == 4
    # Advance past window.
    assert f.rate("CP-1", 20.0) == 0


def test_flapping_above_limit() -> None:
    f = FlapDetector(window_sec=10.0, limit=3)
    assert f.is_flapping("CP-X", 0.0) is False
    for i in range(5):
        f.record("CP-X", float(i))
    assert f.rate("CP-X", 4.0) == 5
    assert f.is_flapping("CP-X", 4.0) is True


def test_reset_clears_history() -> None:
    f = FlapDetector(window_sec=10.0, limit=1)
    f.record("CP-1", 0.0)
    f.record("CP-1", 1.0)
    f.reset("CP-1")
    assert f.rate("CP-1", 2.0) == 0


def test_per_station_counters_are_independent() -> None:
    f = FlapDetector(window_sec=10.0, limit=1)
    for ts in [0.0, 1.0, 2.0]:
        f.record("CP-A", ts)
    assert f.is_flapping("CP-A", 2.0) is True
    assert f.rate("CP-B", 2.0) == 0
