from __future__ import annotations

from ocpp_bench.sim.report import CsmsSnapshot, Report, summarise


def test_summarise_empty_returns_none() -> None:
    assert summarise([]) is None


def test_percentiles_match_known_values() -> None:
    samples = [float(x) for x in range(1, 101)]  # 1..100
    s = summarise(samples)
    assert s is not None
    assert s.count == 100
    assert s.min_sec == 1.0
    assert s.max_sec == 100.0
    # Linear interpolation: p50 of 1..100 is 50.5.
    assert abs(s.p50_sec - 50.5) < 1e-9
    # p95 of 1..100 under this method is 95.05.
    assert abs(s.p95_sec - 95.05) < 1e-9


def test_report_json_roundtrip() -> None:
    r = Report(
        scenario="normal",
        passed=True,
        assertions=["a"],
        failures=[],
        latency={},
        stats={"stations": 1},
        csms=CsmsSnapshot(stations=1, quarantined=0, total_reconnects=0, queue_drops=0),
    )
    body = r.to_json()
    assert '"scenario": "normal"' in body
    assert '"passed": true' in body


def test_report_table_includes_failures() -> None:
    r = Report(
        scenario="normal",
        passed=False,
        assertions=["x"],
        failures=["boom"],
        latency={},
        stats={},
    )
    text = r.to_table()
    assert "failures:" in text
    assert "boom" in text


def test_report_table_includes_latency_and_stats() -> None:
    r = Report(
        scenario="soak",
        passed=True,
        assertions=["a"],
        failures=[],
        latency={"heartbeat": summarise([0.1, 0.2, 0.3])},  # type: ignore[dict-item]
        stats={"stations": 3, "note": "hello"},
        csms=CsmsSnapshot(stations=3, quarantined=1, total_reconnects=4, queue_drops=0),
    )
    text = r.to_table()
    assert "heartbeat" in text
    assert "note: hello" in text
    assert "quarantined:" in text
    assert "4" in text


def test_percentile_single_value() -> None:
    s = summarise([2.5])
    assert s is not None
    assert s.p50_sec == 2.5
    assert s.p95_sec == 2.5
    assert s.p99_sec == 2.5


def test_report_json_omits_none_csms() -> None:
    r = Report(
        scenario="normal",
        passed=True,
        assertions=[],
        failures=[],
        latency={},
        stats={},
    )
    assert '"csms": {}' in r.to_json()
