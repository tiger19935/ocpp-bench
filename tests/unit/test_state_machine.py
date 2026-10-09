from __future__ import annotations

import pytest

from ocpp_bench.protocol import StationFSM, StationState, Trigger, allowed_transitions


def test_initial_state_is_disconnected() -> None:
    assert StationFSM().state is StationState.DISCONNECTED


@pytest.mark.parametrize(("src", "trg", "dst"), allowed_transitions())
def test_every_declared_transition_fires(
    src: StationState, trg: Trigger, dst: StationState
) -> None:
    fsm = StationFSM(state=src)
    r = fsm.transition(trg)
    assert r.allowed is True
    assert r.current is dst
    assert r.previous is src


def test_full_session_sequence() -> None:
    fsm = StationFSM()
    for trg, expected in [
        (Trigger.WS_OPEN, StationState.BOOTING),
        (Trigger.BOOT_ACCEPTED, StationState.AVAILABLE),
        (Trigger.STATUS_PREPARING, StationState.PREPARING),
        (Trigger.START_TXN, StationState.CHARGING),
        (Trigger.STATUS_SUSPENDED_EV, StationState.SUSPENDED_EV),
        (Trigger.STATUS_CHARGING, StationState.CHARGING),
        (Trigger.STOP_TXN, StationState.FINISHING),
        (Trigger.STATUS_AVAILABLE, StationState.AVAILABLE),
        (Trigger.WS_CLOSE, StationState.DISCONNECTED),
    ]:
        assert fsm.transition(trg).current is expected


@pytest.mark.parametrize(
    ("state", "trigger"),
    [
        (StationState.DISCONNECTED, Trigger.BOOT_ACCEPTED),
        (StationState.DISCONNECTED, Trigger.START_TXN),
        (StationState.BOOTING, Trigger.STOP_TXN),
        (StationState.AVAILABLE, Trigger.STOP_TXN),
        (StationState.CHARGING, Trigger.START_TXN),
        (StationState.FINISHING, Trigger.START_TXN),
        (StationState.QUARANTINED, Trigger.START_TXN),
    ],
)
def test_invalid_transitions_are_rejected(state: StationState, trigger: Trigger) -> None:
    fsm = StationFSM(state=state)
    r = fsm.transition(trigger)
    assert r.allowed is False
    assert r.current is state


def test_ws_close_from_any_state() -> None:
    for s in StationState:
        if s is StationState.DISCONNECTED:
            continue
        fsm = StationFSM(state=s)
        assert fsm.transition(Trigger.WS_CLOSE).current is StationState.DISCONNECTED


def test_quarantine_blocks_other_transitions_until_cleared() -> None:
    fsm = StationFSM(state=StationState.CHARGING)
    assert fsm.transition(Trigger.QUARANTINE_SET).current is StationState.QUARANTINED
    assert fsm.transition(Trigger.STATUS_PREPARING).allowed is False
    assert fsm.transition(Trigger.QUARANTINE_CLEARED).current is StationState.AVAILABLE


def test_unresponsive_cleared_by_message() -> None:
    fsm = StationFSM(state=StationState.CHARGING)
    assert fsm.transition(Trigger.CALL_TIMEOUT).current is StationState.UNRESPONSIVE
    assert fsm.transition(Trigger.MESSAGE_RECEIVED).current is StationState.AVAILABLE


def test_idempotent_status_available_in_available() -> None:
    fsm = StationFSM(state=StationState.AVAILABLE)
    r = fsm.transition(Trigger.STATUS_AVAILABLE)
    assert r.allowed is True
    assert r.current is StationState.AVAILABLE


def test_history_records_all_attempts() -> None:
    fsm = StationFSM()
    fsm.transition(Trigger.WS_OPEN)
    fsm.transition(Trigger.STOP_TXN)
    fsm.transition(Trigger.BOOT_ACCEPTED)
    assert len(fsm.history) == 3
    assert [h.allowed for h in fsm.history] == [True, False, True]
