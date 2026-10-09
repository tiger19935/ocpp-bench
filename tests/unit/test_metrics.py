from __future__ import annotations

from ocpp_bench.metrics import build_metrics, render

EXPECTED = {
    "ocpp_bench_stations_connected",
    "ocpp_bench_stations_quarantined",
    "ocpp_bench_messages_total",
    "ocpp_bench_reconnects_total",
    "ocpp_bench_queue_drops_total",
    "ocpp_bench_call_latency_seconds_bucket",
    "ocpp_bench_call_timeouts_total",
}


def test_metric_names_are_stable() -> None:
    m = build_metrics()
    m.stations_connected.inc(1)
    m.stations_quarantined.inc(1)
    m.messages_total.labels(direction="in", action="Heartbeat", protocol="ocpp1.6").inc()
    m.reconnects_total.labels(protocol="ocpp1.6").inc()
    m.queue_drops_total.labels(charge_point_id="CP-1").inc()
    m.call_latency_seconds.labels(action="Heartbeat", protocol="ocpp1.6").observe(0.01)
    m.call_timeouts_total.labels(action="Reset", protocol="ocpp1.6").inc()
    rendered = render(m).decode("utf-8")
    for name in EXPECTED:
        assert name in rendered, f"metric {name} not emitted"


def test_render_latency_histogram_buckets() -> None:
    m = build_metrics()
    m.call_latency_seconds.labels(action="BootNotification", protocol="ocpp1.6").observe(0.012)
    rendered = render(m).decode("utf-8")
    assert 'ocpp_bench_call_latency_seconds_bucket{action="BootNotification"' in rendered
