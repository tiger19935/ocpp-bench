from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ocpp.routing import on
from ocpp.v16 import ChargePoint as ChargePointV16
from ocpp.v16 import call_result as cr16
from ocpp.v16.enums import Action as Action16
from ocpp.v16.enums import RegistrationStatus
from ocpp.v201 import ChargePoint as ChargePointV201
from ocpp.v201 import call_result as cr201
from ocpp.v201.enums import Action as Action201
from ocpp.v201.enums import RegistrationStatusEnumType
from websockets.asyncio.server import ServerConnection

from ocpp_bench.config import Settings
from ocpp_bench.csms.stations import Station
from ocpp_bench.logging import get_logger
from ocpp_bench.protocol import Trigger

logger = get_logger("csms.handlers")


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CsmsChargePointV16(ChargePointV16):  # type: ignore[misc]
    def __init__(
        self,
        cp_id: str,
        connection: ServerConnection,
        station: Station,
        settings: Settings,
    ) -> None:
        super().__init__(cp_id, connection)
        self.station = station
        self.settings = settings
        self.heartbeat_interval = 60

    @on(Action16.boot_notification)
    async def on_boot_notification(
        self,
        charge_point_vendor: str,
        charge_point_model: str,
        **_: Any,
    ) -> cr16.BootNotification:
        self.station.fsm.transition(Trigger.BOOT_ACCEPTED)
        logger.info(
            "boot accepted",
            vendor=charge_point_vendor,
            model=charge_point_model,
            interval=self.heartbeat_interval,
        )
        return cr16.BootNotification(
            current_time=_utcnow_iso(),
            interval=self.heartbeat_interval,
            status=RegistrationStatus.accepted,
        )

    @on(Action16.heartbeat)
    async def on_heartbeat(self, **_: Any) -> cr16.Heartbeat:
        return cr16.Heartbeat(current_time=_utcnow_iso())


class CsmsChargePointV201(ChargePointV201):  # type: ignore[misc]
    def __init__(
        self,
        cp_id: str,
        connection: ServerConnection,
        station: Station,
        settings: Settings,
    ) -> None:
        super().__init__(cp_id, connection)
        self.station = station
        self.settings = settings
        self.heartbeat_interval = 60

    @on(Action201.boot_notification)
    async def on_boot_notification(
        self,
        charging_station: dict[str, Any],
        reason: str,
        **_: Any,
    ) -> cr201.BootNotification:
        self.station.fsm.transition(Trigger.BOOT_ACCEPTED)
        logger.info(
            "boot accepted",
            vendor=charging_station.get("vendor_name"),
            model=charging_station.get("model"),
            reason=reason,
        )
        return cr201.BootNotification(
            current_time=_utcnow_iso(),
            interval=self.heartbeat_interval,
            status=RegistrationStatusEnumType.accepted,
        )

    @on(Action201.heartbeat)
    async def on_heartbeat(self, **_: Any) -> cr201.Heartbeat:
        return cr201.Heartbeat(current_time=_utcnow_iso())
