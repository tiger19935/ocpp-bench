from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiohttp import web

from ocpp_bench.csms.connection import CsmsChargePointV16, CsmsChargePointV201
from ocpp_bench.metrics import render
from ocpp_bench.protocol import (
    CallTimeout,
    CsmsError,
    StationNotConnected,
)

if TYPE_CHECKING:
    from ocpp_bench.csms.server import CsmsServer

_SERVER_KEY: web.AppKey[Any] = web.AppKey("csms")


def build_admin_app(server: CsmsServer) -> web.Application:
    app = web.Application()
    app[_SERVER_KEY] = server
    app.router.add_get("/metrics", _metrics)
    app.router.add_get("/stations", _stations)
    app.router.add_get("/stations/{cp_id}", _station)
    app.router.add_post("/stations/{cp_id}/remote-start", _remote_start)
    app.router.add_post("/stations/{cp_id}/remote-stop", _remote_stop)
    app.router.add_post("/stations/{cp_id}/reset", _reset)
    return app


async def _metrics(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    body = render(server.metrics)
    return web.Response(body=body, content_type="text/plain; version=0.0.4", charset="utf-8")


async def _stations(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    out = []
    async for s in server.store.iter_stations():
        out.append(
            {
                "charge_point_id": s.charge_point_id,
                "protocol": s.protocol,
                "state": str(s.fsm.state),
                "reconnects": s.reconnects,
                "quarantined": s.quarantined,
                "queue_drops": s.queue_drops,
                "connected": server.get_connection(s.charge_point_id) is not None,
            }
        )
    return web.json_response({"stations": out})


async def _station(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    cp_id = request.match_info["cp_id"]
    s = await server.store.get(cp_id)
    if s is None:
        raise web.HTTPNotFound(reason=f"station {cp_id} not found")
    return web.json_response(
        {
            "charge_point_id": s.charge_point_id,
            "protocol": s.protocol,
            "state": str(s.fsm.state),
            "reconnects": s.reconnects,
            "quarantined": s.quarantined,
            "queue_drops": s.queue_drops,
            "connected": server.get_connection(s.charge_point_id) is not None,
        }
    )


def _require_connected(server: CsmsServer, cp_id: str) -> CsmsChargePointV16 | CsmsChargePointV201:
    cp = server.get_connection(cp_id)
    if cp is None:
        raise StationNotConnected(cp_id)
    return cp


async def _remote_start(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    cp_id = request.match_info["cp_id"]
    data = await request.json()
    id_tag = str(data["id_tag"])
    connector_id = int(data["connector_id"]) if "connector_id" in data else None
    try:
        cp = _require_connected(server, cp_id)
        if isinstance(cp, CsmsChargePointV16):
            r = await cp.remote_start(id_tag=id_tag, connector_id=connector_id)
            return web.json_response({"status": r.status})
        remote_start_id = int(data.get("remote_start_id", 1))
        r201 = await cp.request_start_transaction(
            id_token=id_tag, remote_start_id=remote_start_id, evse_id=connector_id
        )
        return web.json_response({"status": r201.status})
    except StationNotConnected as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except CallTimeout as exc:
        raise web.HTTPGatewayTimeout(reason=str(exc)) from exc
    except CsmsError as exc:
        raise web.HTTPBadGateway(reason=str(exc)) from exc


async def _remote_stop(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    cp_id = request.match_info["cp_id"]
    data = await request.json()
    try:
        cp = _require_connected(server, cp_id)
        if isinstance(cp, CsmsChargePointV16):
            r = await cp.remote_stop(transaction_id=int(data["transaction_id"]))
            return web.json_response({"status": r.status})
        r201 = await cp.request_stop_transaction(transaction_id=str(data["transaction_id"]))
        return web.json_response({"status": r201.status})
    except StationNotConnected as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except CallTimeout as exc:
        raise web.HTTPGatewayTimeout(reason=str(exc)) from exc


async def _reset(request: web.Request) -> web.Response:
    server = request.app[_SERVER_KEY]
    cp_id = request.match_info["cp_id"]
    try:
        cp = _require_connected(server, cp_id)
        if isinstance(cp, CsmsChargePointV16):
            r = await cp.reset()
            return web.json_response({"status": r.status})
        # 2.0.1 reset: not wired as a server method here; the admin surface
        # focuses on operations with equivalent 1.6 and 2.0.1 handling.
        raise web.HTTPNotImplemented(reason="reset not implemented for 2.0.1 in this build")
    except StationNotConnected as exc:
        raise web.HTTPNotFound(reason=str(exc)) from exc
    except CallTimeout as exc:
        raise web.HTTPGatewayTimeout(reason=str(exc)) from exc
