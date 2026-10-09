from __future__ import annotations

import pytest
from pydantic import ValidationError

from ocpp_bench.sim.scenarios import (
    BurstScenario,
    NormalScenario,
    SoakScenario,
    load_scenario,
)


def test_normal_minimal() -> None:
    s = load_scenario({"type": "normal", "stations": 5})
    assert isinstance(s, NormalScenario)
    assert s.cfg.stations == 5


def test_soak_minimal() -> None:
    s = load_scenario({"type": "soak", "stations": 10, "duration_sec": 30})
    assert isinstance(s, SoakScenario)
    assert s.cfg.duration_sec == 30


def test_burst_minimal() -> None:
    s = load_scenario({"type": "burst", "stations": 10})
    assert isinstance(s, BurstScenario)
    assert s.cfg.heartbeat_interval_sec == 1.0
    assert s.cfg.metervalue_interval_sec == 2.0


def test_unknown_type_rejected() -> None:
    with pytest.raises(ValidationError):
        load_scenario({"type": "something-else", "stations": 1})


def test_bad_stations_rejected() -> None:
    with pytest.raises(ValidationError):
        load_scenario({"type": "normal", "stations": 0})


def test_unknown_fields_ignored_or_rejected() -> None:
    with pytest.raises(ValidationError):
        load_scenario({"type": "normal", "stations": 1, "foo": "bar"})
