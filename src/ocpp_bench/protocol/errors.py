from __future__ import annotations


class CsmsError(Exception):
    """Base class for CSMS-level errors raised at our handler boundary."""


class CallTimeout(CsmsError):
    def __init__(self, charge_point_id: str, action: str, timeout_sec: float) -> None:
        super().__init__(
            f"station {charge_point_id} did not answer {action} within {timeout_sec:.1f}s"
        )
        self.charge_point_id = charge_point_id
        self.action = action
        self.timeout_sec = timeout_sec


class StationNotConnected(CsmsError):
    def __init__(self, charge_point_id: str) -> None:
        super().__init__(f"station {charge_point_id} is not currently connected")
        self.charge_point_id = charge_point_id


class StationUnresponsive(CsmsError):
    def __init__(self, charge_point_id: str) -> None:
        super().__init__(f"station {charge_point_id} is marked unresponsive")
        self.charge_point_id = charge_point_id


class StationQuarantined(CsmsError):
    def __init__(self, charge_point_id: str) -> None:
        super().__init__(f"station {charge_point_id} is quarantined")
        self.charge_point_id = charge_point_id
