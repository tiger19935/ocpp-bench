from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

# All metric names start with ocpp_bench_ so a shared Prometheus has no name
# collisions, and the names are stable (tested) so dashboards don't drift.
_LATENCY_BUCKETS: Final[tuple[float, ...]] = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
)


@dataclass
class Metrics:
    registry: CollectorRegistry
    stations_connected: Gauge
    stations_quarantined: Gauge
    messages_total: Counter
    reconnects_total: Counter
    queue_drops_total: Counter
    call_latency_seconds: Histogram
    call_timeouts_total: Counter


def build_metrics(registry: CollectorRegistry | None = None) -> Metrics:
    reg = registry if registry is not None else CollectorRegistry()
    return Metrics(
        registry=reg,
        stations_connected=Gauge(
            "ocpp_bench_stations_connected",
            "Number of charge points currently connected",
            registry=reg,
        ),
        stations_quarantined=Gauge(
            "ocpp_bench_stations_quarantined",
            "Number of charge points currently quarantined due to flap",
            registry=reg,
        ),
        messages_total=Counter(
            "ocpp_bench_messages_total",
            "OCPP messages handled by the CSMS",
            labelnames=("direction", "action", "protocol"),
            registry=reg,
        ),
        reconnects_total=Counter(
            "ocpp_bench_reconnects_total",
            "Total websocket reconnects",
            labelnames=("protocol",),
            registry=reg,
        ),
        queue_drops_total=Counter(
            "ocpp_bench_queue_drops_total",
            "CALLs dropped due to inbound queue overflow",
            labelnames=("charge_point_id",),
            registry=reg,
        ),
        call_latency_seconds=Histogram(
            "ocpp_bench_call_latency_seconds",
            "Round-trip time of OCPP calls, in seconds",
            labelnames=("action", "protocol"),
            buckets=_LATENCY_BUCKETS,
            registry=reg,
        ),
        call_timeouts_total=Counter(
            "ocpp_bench_call_timeouts_total",
            "Server-initiated CALLs that timed out",
            labelnames=("action", "protocol"),
            registry=reg,
        ),
    )


def render(metrics: Metrics) -> bytes:
    return generate_latest(metrics.registry)
