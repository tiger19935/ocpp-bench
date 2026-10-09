from __future__ import annotations

import json

import structlog

from ocpp_bench.logging import bind_station, configure, get_logger, unbind_station


def test_json_output_includes_bound_station(capfd: object) -> None:
    configure(level="info", json_output=True)
    bind_station("CP-42")
    log = get_logger("test")
    log.info("hello", action="BootNotification")
    unbind_station()

    err = capfd.readouterr().err  # type: ignore[attr-defined]
    lines = [line for line in err.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["charge_point_id"] == "CP-42"
    assert payload["event"] == "hello"
    assert payload["action"] == "BootNotification"
    assert payload["level"] == "info"


def test_unbind_removes_station(capfd: object) -> None:
    configure(level="info", json_output=True)
    bind_station("CP-1")
    unbind_station()
    structlog.get_logger("test").info("after")
    err = capfd.readouterr().err  # type: ignore[attr-defined]
    payload = json.loads(err.splitlines()[-1])
    assert "charge_point_id" not in payload
