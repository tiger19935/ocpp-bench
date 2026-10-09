from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from ocpp.routing import on
from ocpp.v16 import ChargePoint as ChargePointV16
from ocpp.v16 import call_result as cr16
from ocpp.v16.datatypes import IdTagInfo
from ocpp.v16.enums import Action as Action16
from ocpp.v16.enums import AuthorizationStatus, ChargePointStatus, RegistrationStatus
from ocpp.v201 import ChargePoint as ChargePointV201
from ocpp.v201 import call as call201
from ocpp.v201 import call_result as cr201
from ocpp.v201.datatypes import IdTokenInfoType
from ocpp.v201.enums import Action as Action201
from ocpp.v201.enums import (
    AuthorizationStatusEnumType,
    ConnectorStatusEnumType,
    RegistrationStatusEnumType,
    RequestStartStopStatusEnumType,
    TransactionEventEnumType,
)
from websockets.asyncio.server import ServerConnection

from ocpp_bench.config import Settings
from ocpp_bench.csms.sessions import SessionStore
from ocpp_bench.csms.stations import Station
from ocpp_bench.logging import get_logger
from ocpp_bench.protocol import Trigger

logger = get_logger("csms.handlers")

_STATUS_TRIGGERS: dict[ChargePointStatus, Trigger] = {
    ChargePointStatus.available: Trigger.STATUS_AVAILABLE,
    ChargePointStatus.preparing: Trigger.STATUS_PREPARING,
    ChargePointStatus.charging: Trigger.STATUS_CHARGING,
    ChargePointStatus.suspended_ev: Trigger.STATUS_SUSPENDED_EV,
    ChargePointStatus.suspended_evse: Trigger.STATUS_SUSPENDED_EVSE,
    ChargePointStatus.finishing: Trigger.STATUS_FINISHING,
    ChargePointStatus.faulted: Trigger.STATUS_FAULTED,
}


def _utcnow_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CsmsChargePointV16(ChargePointV16):  # type: ignore[misc]
    def __init__(
        self,
        cp_id: str,
        connection: ServerConnection,
        station: Station,
        settings: Settings,
        sessions: SessionStore,
    ) -> None:
        super().__init__(cp_id, connection)
        self.station = station
        self.settings = settings
        self.sessions = sessions
        self.heartbeat_interval = 60

    @on(Action16.boot_notification)
    async def on_boot_notification(
        self,
        charge_point_vendor: str,
        charge_point_model: str,
        **_: Any,
    ) -> cr16.BootNotification:
        self.station.fsm.transition(Trigger.BOOT_ACCEPTED)
        logger.info("boot accepted", vendor=charge_point_vendor, model=charge_point_model)
        return cr16.BootNotification(
            current_time=_utcnow_iso(),
            interval=self.heartbeat_interval,
            status=RegistrationStatus.accepted,
        )

    @on(Action16.heartbeat)
    async def on_heartbeat(self, **_: Any) -> cr16.Heartbeat:
        return cr16.Heartbeat(current_time=_utcnow_iso())

    @on(Action16.authorize)
    async def on_authorize(self, id_tag: str, **_: Any) -> cr16.Authorize:
        logger.info("authorize", id_tag=id_tag)
        return cr16.Authorize(id_tag_info=IdTagInfo(status=AuthorizationStatus.accepted))

    @on(Action16.status_notification)
    async def on_status_notification(
        self,
        connector_id: int,
        error_code: str,
        status: str,
        **_: Any,
    ) -> cr16.StatusNotification:
        trg = _STATUS_TRIGGERS.get(ChargePointStatus(status))
        if trg is not None:
            self.station.fsm.transition(trg)
        logger.info(
            "status notification",
            connector_id=connector_id,
            status=status,
            error_code=error_code,
            fsm=self.station.fsm.state,
        )
        return cr16.StatusNotification()

    @on(Action16.start_transaction)
    async def on_start_transaction(
        self,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        timestamp: str,
        **_: Any,
    ) -> cr16.StartTransaction:
        txn = await self.sessions.open(
            charge_point_id=self.id,
            connector_id=connector_id,
            id_tag=id_tag,
            meter_start=meter_start,
            now=time.monotonic(),
        )
        self.station.fsm.transition(Trigger.START_TXN)
        logger.info(
            "start transaction",
            transaction_id=txn.transaction_id,
            connector_id=connector_id,
            id_tag=id_tag,
            timestamp=timestamp,
        )
        return cr16.StartTransaction(
            transaction_id=txn.transaction_id,
            id_tag_info=IdTagInfo(status=AuthorizationStatus.accepted),
        )

    @on(Action16.stop_transaction)
    async def on_stop_transaction(
        self,
        meter_stop: int,
        timestamp: str,
        transaction_id: int,
        **_: Any,
    ) -> cr16.StopTransaction:
        txn = await self.sessions.close(transaction_id)
        self.station.fsm.transition(Trigger.STOP_TXN)
        logger.info(
            "stop transaction",
            transaction_id=transaction_id,
            meter_stop=meter_stop,
            timestamp=timestamp,
            known=txn is not None,
        )
        return cr16.StopTransaction(id_tag_info=IdTagInfo(status=AuthorizationStatus.accepted))

    @on(Action16.meter_values)
    async def on_meter_values(
        self,
        connector_id: int,
        meter_value: list[dict[str, Any]],
        **_: Any,
    ) -> cr16.MeterValues:
        logger.debug("meter values", connector_id=connector_id, count=len(meter_value))
        return cr16.MeterValues()


class CsmsChargePointV201(ChargePointV201):  # type: ignore[misc]
    def __init__(
        self,
        cp_id: str,
        connection: ServerConnection,
        station: Station,
        settings: Settings,
        sessions: SessionStore,
    ) -> None:
        super().__init__(cp_id, connection)
        self.station = station
        self.settings = settings
        self.sessions = sessions
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

    @on(Action201.authorize)
    async def on_authorize(self, id_token: dict[str, Any], **_: Any) -> cr201.Authorize:
        logger.info("authorize", id_token=id_token.get("id_token"))
        return cr201.Authorize(
            id_token_info=IdTokenInfoType(status=AuthorizationStatusEnumType.accepted)
        )

    @on(Action201.status_notification)
    async def on_status_notification(
        self,
        timestamp: str,
        connector_status: str,
        evse_id: int,
        connector_id: int,
        **_: Any,
    ) -> cr201.StatusNotification:
        trg = _CONNECTOR_STATUS_TRIGGERS.get(ConnectorStatusEnumType(connector_status))
        if trg is not None:
            self.station.fsm.transition(trg)
        logger.info(
            "status notification",
            evse_id=evse_id,
            connector_id=connector_id,
            connector_status=connector_status,
            timestamp=timestamp,
            fsm=self.station.fsm.state,
        )
        return cr201.StatusNotification()

    @on(Action201.meter_values)
    async def on_meter_values(
        self,
        evse_id: int,
        meter_value: list[dict[str, Any]],
        **_: Any,
    ) -> cr201.MeterValues:
        logger.debug("meter values", evse_id=evse_id, count=len(meter_value))
        return cr201.MeterValues()

    @on(Action201.transaction_event)
    async def on_transaction_event(
        self,
        event_type: str,
        timestamp: str,
        trigger_reason: str,
        seq_no: int,
        transaction_info: dict[str, Any],
        **kwargs: Any,
    ) -> cr201.TransactionEvent:
        txn_id = transaction_info.get("transaction_id")
        event = TransactionEventEnumType(event_type)
        if event is TransactionEventEnumType.started:
            evse = kwargs.get("evse", {}) or {}
            connector_id = int(evse.get("connector_id", 1))
            id_token = (kwargs.get("id_token") or {}).get("id_token", "")
            await self.sessions.open(
                charge_point_id=self.id,
                connector_id=connector_id,
                id_tag=id_token,
                meter_start=0,
                now=time.monotonic(),
            )
            self.station.fsm.transition(Trigger.START_TXN)
        elif event is TransactionEventEnumType.ended and txn_id is not None:
            with_int = _parse_int_or_none(txn_id)
            if with_int is not None:
                await self.sessions.close(with_int)
            self.station.fsm.transition(Trigger.STOP_TXN)
        logger.info(
            "transaction event",
            event_type=event_type,
            trigger_reason=trigger_reason,
            seq_no=seq_no,
            transaction_id=txn_id,
            timestamp=timestamp,
        )
        return cr201.TransactionEvent()

    async def request_start_transaction(
        self, id_token: str, remote_start_id: int, evse_id: int | None = None
    ) -> cr201.RequestStartTransaction:
        payload = call201.RequestStartTransaction(
            id_token={"id_token": id_token, "type": "Central"},
            remote_start_id=remote_start_id,
            evse_id=evse_id,
        )
        return await self.call(payload)

    async def request_stop_transaction(self, transaction_id: str) -> cr201.RequestStopTransaction:
        payload = call201.RequestStopTransaction(transaction_id=transaction_id)
        return await self.call(payload)


_CONNECTOR_STATUS_TRIGGERS: dict[ConnectorStatusEnumType, Trigger] = {
    ConnectorStatusEnumType.available: Trigger.STATUS_AVAILABLE,
    ConnectorStatusEnumType.occupied: Trigger.STATUS_CHARGING,
    ConnectorStatusEnumType.faulted: Trigger.STATUS_FAULTED,
    ConnectorStatusEnumType.unavailable: Trigger.STATUS_AVAILABLE,
    ConnectorStatusEnumType.reserved: Trigger.STATUS_AVAILABLE,
}


def _parse_int_or_none(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


_ = RequestStartStopStatusEnumType  # used in server-initiated flows
