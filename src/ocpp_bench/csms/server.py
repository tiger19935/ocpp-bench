from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Response
from websockets.typing import Subprotocol

from ocpp_bench.config import Protocol, Settings
from ocpp_bench.csms.connection import CsmsChargePointV16, CsmsChargePointV201
from ocpp_bench.csms.sessions import SessionStore
from ocpp_bench.csms.stations import InMemoryStationStore, Station, StationStore
from ocpp_bench.logging import bind_station, clear, get_logger, unbind_station
from ocpp_bench.protocol import Trigger

logger = get_logger("csms.server")

_SUBPROTOCOL_16 = Subprotocol("ocpp1.6")
_SUBPROTOCOL_201 = Subprotocol("ocpp2.0.1")
_PATH_RE = re.compile(r"^/ocpp/(?P<cp_id>[A-Za-z0-9_\-.:]{1,64})/?$")


@dataclass
class CsmsServer:
    settings: Settings
    store: StationStore
    sessions: SessionStore
    _connections: dict[str, CsmsChargePointV16 | CsmsChargePointV201] = field(default_factory=dict)

    @classmethod
    def from_settings(cls, settings: Settings) -> CsmsServer:
        return cls(
            settings=settings,
            store=InMemoryStationStore(),
            sessions=SessionStore(duplicate_window_sec=settings.duplicate_start_window_sec),
        )

    def get_connection(self, cp_id: str) -> CsmsChargePointV16 | CsmsChargePointV201 | None:
        return self._connections.get(cp_id)

    def _supported_subprotocols(self) -> list[Subprotocol]:
        match self.settings.protocol:
            case Protocol.V16:
                return [_SUBPROTOCOL_16]
            case Protocol.V201:
                return [_SUBPROTOCOL_201]
            case Protocol.BOTH:
                return [_SUBPROTOCOL_16, _SUBPROTOCOL_201]

    def _select_subprotocol(
        self, _ws: ServerConnection, client_offered: Sequence[Subprotocol]
    ) -> Subprotocol | None:
        for sp in self._supported_subprotocols():
            if sp in client_offered:
                return sp
        return None

    def _process_request(self, ws: ServerConnection, request: object) -> Response | None:
        del request
        req = ws.request
        if req is None:
            return None
        if not _PATH_RE.match(req.path):
            logger.warning("rejecting bad path", path=req.path)
            return ws.respond(404, "unknown path\n")
        # websockets 13 accepts a client that offers only subprotocols we don't
        # support and completes the handshake with no Sec-WebSocket-Protocol
        # header. OCPP requires rejection: a station that expects to speak 1.6
        # or 2.0.1 must not be left speaking "nothing".
        offered = _parse_subprotocols(req.headers.get("Sec-WebSocket-Protocol"))
        if offered and not any(sp in offered for sp in self._supported_subprotocols()):
            logger.warning("rejecting unknown subprotocol", offered=offered)
            return ws.respond(400, "unsupported subprotocol\n")
        return None

    async def _handler(self, ws: ServerConnection) -> None:
        path = ws.request.path if ws.request else ""
        m = _PATH_RE.match(path)
        if m is None:
            # Belt and braces: process_request already covered this.
            await ws.close(code=1008, reason="bad path")
            return
        cp_id = m.group("cp_id")
        subprotocol = ws.subprotocol
        if subprotocol not in {_SUBPROTOCOL_16, _SUBPROTOCOL_201}:
            # websockets would have refused the handshake with 400 already,
            # but if a client bypasses negotiation this gives a clean close.
            await ws.close(code=1002, reason="unsupported subprotocol")
            return

        station = await self.store.upsert(cp_id, protocol=str(subprotocol))
        station.fsm.transition(Trigger.WS_OPEN)
        bind_station(cp_id, protocol=str(subprotocol))
        logger.info("station connected", path=path)

        cp = _build_chargepoint(cp_id, ws, subprotocol, station, self.settings, self.sessions)
        self._connections[cp_id] = cp
        try:
            await cp.start()
        except ConnectionClosed:
            pass
        finally:
            self._connections.pop(cp_id, None)
            station.fsm.transition(Trigger.WS_CLOSE)
            logger.info("station disconnected")
            unbind_station()
            clear()

    async def serve(self, stop: asyncio.Future[None] | None = None) -> None:
        async with serve(
            self._handler,
            host=self.settings.host,
            port=self.settings.port,
            subprotocols=self._supported_subprotocols(),
            select_subprotocol=self._select_subprotocol,
            process_request=self._process_request,
            # Our own bounded queue sits one layer above; the websockets-layer
            # queue stays small to shed obviously broken clients.
            max_queue=32,
            ping_interval=20,
            ping_timeout=20,
        ) as server:
            logger.info(
                "csms listening",
                host=self.settings.host,
                port=self.settings.port,
                protocols=[str(sp) for sp in self._supported_subprotocols()],
            )
            if stop is None:
                await server.serve_forever()
            else:
                await stop


def _build_chargepoint(
    cp_id: str,
    ws: ServerConnection,
    subprotocol: Subprotocol,
    station: Station,
    settings: Settings,
    sessions: SessionStore,
) -> CsmsChargePointV16 | CsmsChargePointV201:
    if subprotocol == _SUBPROTOCOL_16:
        return CsmsChargePointV16(cp_id, ws, station, settings, sessions)
    return CsmsChargePointV201(cp_id, ws, station, settings, sessions)


def path_regex() -> re.Pattern[str]:
    return _PATH_RE


def _parse_subprotocols(header: str | None) -> list[str]:
    if not header:
        return []
    return [s.strip() for s in header.split(",") if s.strip()]


__all__ = ["CsmsServer", "path_regex"]
