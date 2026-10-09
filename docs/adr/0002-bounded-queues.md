# ADR 0002: bounded inbound queue, CALLERROR on overflow

## Context

The default websockets server receive loop would read messages as fast as
the socket allows; the `ocpp` library's internal queues are unbounded too.
A single buggy station sending MeterValues at 1000/s then stalls the
dispatcher and the websocket layer's write buffer. The pattern I saw in
production: one charger pins the CPU of its handler coroutine, and the
other chargers' heartbeats start timing out.

## Decision

Each connection gets its own `asyncio.Queue(maxsize=settings.inbound_queue_depth)`
(default 128). Reader and dispatcher are separate tasks. On overflow, the
server emits a `CALLERROR` with the OCPP error code `InternalError` and
description `InboundQueueFull`, increments
`ocpp_bench_queue_drops_total{charge_point_id=…}`, and keeps the
connection open.

## Alternatives considered

- Close the websocket on overflow. Rejected: closing feeds the reconnect
  storm. Chargers reconnect immediately and resume flooding.
- Grow the queue. Rejected: unbounded buffering only delays the problem,
  trades memory for latency, and masks the misbehaviour from metrics.

## Consequences

- Backpressure is a signal to the station, not to the operator. The
  station library observes the CALLERROR and typically slows down or
  surfaces it; the drop counter is the operator's indicator.
- The station is still responsive on the socket, which keeps heartbeats
  alive. See `tests/integration/test_backpressure`.
