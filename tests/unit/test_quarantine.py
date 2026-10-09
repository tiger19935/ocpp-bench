from __future__ import annotations

from ocpp_bench.health import Quarantine


def test_backoff_schedule_doubles_up_to_sixty() -> None:
    assert Quarantine.schedule() == (1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0)


def test_apply_returns_schedule_in_order() -> None:
    q = Quarantine()
    waits = [q.apply("CP-1", t) for t in range(7)]
    assert waits == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0]
    # After the schedule is exhausted the cap holds.
    assert q.apply("CP-1", 100.0) == 60.0


def test_is_quarantined_until_cleared() -> None:
    q = Quarantine(clear_after_sec=5.0)
    q.apply("CP-1", 0.0)
    assert q.is_quarantined("CP-1") is True
    assert q.tick("CP-1", 2.0) is False
    assert q.is_quarantined("CP-1") is True
    assert q.tick("CP-1", 5.5) is True
    assert q.is_quarantined("CP-1") is False


def test_reset_removes_station() -> None:
    q = Quarantine()
    q.apply("CP-1", 0.0)
    q.reset("CP-1")
    assert q.is_quarantined("CP-1") is False


def test_tick_on_unknown_station() -> None:
    q = Quarantine()
    assert q.tick("CP-unknown", 10.0) is False


def test_tick_after_clear_is_noop() -> None:
    q = Quarantine(clear_after_sec=5.0)
    q.apply("CP-1", 0.0)
    assert q.tick("CP-1", 5.5) is True
    # Second tick finds cleared state.
    assert q.tick("CP-1", 10.0) is False
