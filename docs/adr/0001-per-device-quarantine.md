# ADR 0001: per-device quarantine over connection refusal

## Context

In production I ran a network of 500+ chargers. The failures that cost the
most sleep were not single stations breaking — those were obvious. The
expensive ones were a handful of broken chargers flooding the backend with
reconnect attempts, each one triggering boot + status + sometimes
transaction retries, enough to make the healthy 95% jittery. The reflex is
to refuse the connection, but refusal nudges the charger into a tighter
retry loop and never recovers on its own.

## Decision

A station that reconnects more than five times in a 60-second window is
*quarantined*: the connection is accepted and acked, but the station's
state transitions and transaction effects are suppressed, and the next
reconnect is throttled with an exponential backoff of 1, 2, 4, 8, 16, 32,
60 seconds. The quarantine clears after 300 seconds of stability.

Thresholds and the backoff schedule live in Settings; the schedule itself
is tested by `tests/unit/test_quarantine.py`.

## Consequences

- One misbehaving charger cannot flood ingress; the other stations' p95
  heartbeat latency is bounded (see `tests/integration/test_sim_scenarios`
  `test_flapping_isolation`).
- A charger wrongly flagged (bad network, not bad firmware) still
  completes handshake and acks, so it does not thrash. It just loses time.
- Operators can read `/stations` to see who is quarantined and the counter
  `ocpp_bench_stations_quarantined` to alert on it.
