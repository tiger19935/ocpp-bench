from __future__ import annotations

from ocpp.v16 import ChargePoint as ChargePointV16
from ocpp.v201 import ChargePoint as ChargePointV201


class CsmsChargePointV16(ChargePointV16):  # type: ignore[misc]
    """OCPP 1.6J handlers live here. Message handlers are added in later commits."""


class CsmsChargePointV201(ChargePointV201):  # type: ignore[misc]
    """OCPP 2.0.1 handlers live here. Message handlers are added in later commits."""
