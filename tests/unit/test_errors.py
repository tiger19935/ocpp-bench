from __future__ import annotations

from ocpp_bench.protocol import (
    CallTimeout,
    CsmsError,
    StationNotConnected,
    StationQuarantined,
    StationUnresponsive,
)


def test_call_timeout_carries_fields() -> None:
    e = CallTimeout("CP-1", "Reset", 30.0)
    assert e.charge_point_id == "CP-1"
    assert e.action == "Reset"
    assert e.timeout_sec == 30.0
    assert isinstance(e, CsmsError)
    assert "CP-1" in str(e)
    assert "30.0" in str(e)


def test_station_not_connected_message() -> None:
    e = StationNotConnected("CP-2")
    assert e.charge_point_id == "CP-2"
    assert "CP-2" in str(e)


def test_station_unresponsive_message() -> None:
    e = StationUnresponsive("CP-3")
    assert e.charge_point_id == "CP-3"
    assert "unresponsive" in str(e)


def test_station_quarantined_message() -> None:
    e = StationQuarantined("CP-4")
    assert e.charge_point_id == "CP-4"
    assert "quarantined" in str(e)
