from __future__ import annotations

import pytest
from pydantic import ValidationError

from ocpp_bench.config import Protocol, Settings


def test_defaults_match_env_example() -> None:
    s = Settings()
    assert s.host == "0.0.0.0"
    assert s.port == 9000
    assert s.admin_port == 9100
    assert s.protocol is Protocol.BOTH
    assert s.inbound_queue_depth == 128
    assert s.call_timeout_sec == 30.0
    assert s.flap_limit == 5
    assert s.flap_window_sec == 60.0
    assert s.duplicate_start_window_sec == 10.0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCPP_BENCH_PORT", "9100")
    monkeypatch.setenv("OCPP_BENCH_PROTOCOL", "1.6")
    monkeypatch.setenv("OCPP_BENCH_FLAP_LIMIT", "9")
    s = Settings()
    assert s.port == 9100
    assert s.protocol is Protocol.V16
    assert s.flap_limit == 9


def test_bad_port_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCPP_BENCH_PORT", "70000")
    with pytest.raises(ValidationError):
        Settings()
