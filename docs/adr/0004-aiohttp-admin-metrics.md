# ADR 0004: aiohttp for admin and /metrics, separate port

## Context

The CSMS needs an operator surface: list stations, drive remote
start/stop/reset, serve Prometheus. Mounting those on the same port as the
OCPP websocket would mean chargers can reach them, and the HTTP layer
would compete with websockets for the same event loop at the same ingress.

## Decision

Use `aiohttp` as the admin HTTP server, pure asyncio, same event loop as
the websockets server. Bind it on `admin_port` (default 9100). The OCPP
port serves only the websocket.

aiohttp was chosen over Starlette: no ASGI shim, no uvicorn runner, cleaner
mypy strict surface for a small set of handlers.

## Consequences

- Operators point Prometheus at `csms:9100/metrics`.
- Admin endpoints return the HTTP code that matches the condition
  (`404` unknown station, `504` server-initiated call timeout, `502`
  station not connected or quarantined).
- Deploying behind a reverse proxy is straightforward: route 9000 to the
  internet, keep 9100 internal.
