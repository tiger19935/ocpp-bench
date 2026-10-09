# ADR 0003: in-memory state behind a Protocol

## Context

A real CSMS needs durable storage. A reference CSMS used as a test harness
does not — adding a database would obscure the parts I actually want to
exercise (state machine, backpressure, quarantine). But a reviewer should
be able to look at the code and see the seam where storage would land.

## Decision

The server depends on a `StationStore` `typing.Protocol`. The default
implementation is in-memory (`dict` behind an `asyncio.Lock`). Transactions
live in a parallel `SessionStore` with the same shape. The whole process
holds no cross-run state.

## Consequences

- No persistence across restart. Documented in the README as out of scope.
- Swapping in a Postgres-backed store means writing one adapter — the
  tests pin the behavioural contract via the Protocol.
- The simulator can run against the CSMS without any setup — matches the
  "clone and go" goal.
