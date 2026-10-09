from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final


class StationState(StrEnum):
    DISCONNECTED = "disconnected"
    BOOTING = "booting"
    AVAILABLE = "available"
    PREPARING = "preparing"
    CHARGING = "charging"
    SUSPENDED_EV = "suspended_ev"
    SUSPENDED_EVSE = "suspended_evse"
    FINISHING = "finishing"
    FAULTED = "faulted"
    UNRESPONSIVE = "unresponsive"
    QUARANTINED = "quarantined"


class Trigger(StrEnum):
    WS_OPEN = "ws_open"
    WS_CLOSE = "ws_close"
    BOOT_ACCEPTED = "boot_accepted"
    STATUS_AVAILABLE = "status_available"
    STATUS_PREPARING = "status_preparing"
    STATUS_CHARGING = "status_charging"
    STATUS_SUSPENDED_EV = "status_suspended_ev"
    STATUS_SUSPENDED_EVSE = "status_suspended_evse"
    STATUS_FINISHING = "status_finishing"
    STATUS_FAULTED = "status_faulted"
    START_TXN = "start_txn"
    STOP_TXN = "stop_txn"
    CALL_TIMEOUT = "call_timeout"
    MESSAGE_RECEIVED = "message_received"
    QUARANTINE_SET = "quarantine_set"
    QUARANTINE_CLEARED = "quarantine_cleared"


# Explicit allowed transitions. Any (state, trigger) pair not present here is
# rejected without changing state. Keeping this a plain dict (not built up
# from decorators) means a reviewer can read the whole machine in one screen.
_T: Final[dict[tuple[StationState, Trigger], StationState]] = {
    # Connection lifecycle.
    (StationState.DISCONNECTED, Trigger.WS_OPEN): StationState.BOOTING,
    (StationState.BOOTING, Trigger.BOOT_ACCEPTED): StationState.AVAILABLE,
    (StationState.BOOTING, Trigger.WS_CLOSE): StationState.DISCONNECTED,
    # Status notifications: Available is reachable from anything that
    # represents a transient non-fault state, including Faulted → Available
    # recovery (OCPP 1.6 §4.9, StatusNotification).
    (StationState.AVAILABLE, Trigger.STATUS_PREPARING): StationState.PREPARING,
    (StationState.PREPARING, Trigger.STATUS_AVAILABLE): StationState.AVAILABLE,
    (StationState.PREPARING, Trigger.START_TXN): StationState.CHARGING,
    (StationState.AVAILABLE, Trigger.START_TXN): StationState.CHARGING,
    (StationState.CHARGING, Trigger.STATUS_SUSPENDED_EV): StationState.SUSPENDED_EV,
    (StationState.CHARGING, Trigger.STATUS_SUSPENDED_EVSE): StationState.SUSPENDED_EVSE,
    (StationState.SUSPENDED_EV, Trigger.STATUS_CHARGING): StationState.CHARGING,
    (StationState.SUSPENDED_EVSE, Trigger.STATUS_CHARGING): StationState.CHARGING,
    (StationState.SUSPENDED_EV, Trigger.STOP_TXN): StationState.FINISHING,
    (StationState.SUSPENDED_EVSE, Trigger.STOP_TXN): StationState.FINISHING,
    (StationState.CHARGING, Trigger.STOP_TXN): StationState.FINISHING,
    (StationState.CHARGING, Trigger.STATUS_FINISHING): StationState.FINISHING,
    (StationState.FINISHING, Trigger.STATUS_AVAILABLE): StationState.AVAILABLE,
    # Fault handling.
    (StationState.AVAILABLE, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.PREPARING, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.CHARGING, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.SUSPENDED_EV, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.SUSPENDED_EVSE, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.FINISHING, Trigger.STATUS_FAULTED): StationState.FAULTED,
    (StationState.FAULTED, Trigger.STATUS_AVAILABLE): StationState.AVAILABLE,
    # Unresponsive: entered on server-initiated call timeout, cleared on any
    # subsequent inbound message. The target of CALL_TIMEOUT is any state
    # except DISCONNECTED / QUARANTINED.
    (StationState.AVAILABLE, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.PREPARING, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.CHARGING, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.SUSPENDED_EV, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.SUSPENDED_EVSE, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.FINISHING, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.FAULTED, Trigger.CALL_TIMEOUT): StationState.UNRESPONSIVE,
    (StationState.UNRESPONSIVE, Trigger.MESSAGE_RECEIVED): StationState.AVAILABLE,
}

# WS_CLOSE and QUARANTINE_SET are allowed from every non-terminal state. Rather
# than enumerate them above we handle both explicitly in transition().
_UNIVERSAL_TO_DISCONNECTED: Final = frozenset(
    s for s in StationState if s is not StationState.DISCONNECTED
)
_UNIVERSAL_TO_QUARANTINE: Final = frozenset(
    s
    for s in StationState
    if s is not StationState.QUARANTINED and s is not StationState.DISCONNECTED
)


@dataclass
class TransitionResult:
    allowed: bool
    previous: StationState
    current: StationState
    trigger: Trigger


@dataclass
class StationFSM:
    state: StationState = StationState.DISCONNECTED
    history: list[TransitionResult] = field(default_factory=list, repr=False)

    def transition(self, trigger: Trigger) -> TransitionResult:
        prev = self.state
        new = self._resolve(prev, trigger)
        allowed = new != prev or _is_self_loop(prev, trigger)
        if new != prev:
            self.state = new
        result = TransitionResult(
            allowed=allowed if new is not None else False,
            previous=prev,
            current=self.state,
            trigger=trigger,
        )
        self.history.append(result)
        return result

    def _resolve(self, state: StationState, trigger: Trigger) -> StationState:
        if trigger is Trigger.WS_CLOSE and state in _UNIVERSAL_TO_DISCONNECTED:
            return StationState.DISCONNECTED
        if trigger is Trigger.QUARANTINE_SET and state in _UNIVERSAL_TO_QUARANTINE:
            return StationState.QUARANTINED
        if trigger is Trigger.QUARANTINE_CLEARED and state is StationState.QUARANTINED:
            return StationState.AVAILABLE
        return _T.get((state, trigger), state)


def _is_self_loop(state: StationState, trigger: Trigger) -> bool:
    # STATUS_AVAILABLE in AVAILABLE and STATUS_CHARGING in CHARGING are
    # idempotent and still count as allowed (chargers resend status).
    idempotent = {
        (StationState.AVAILABLE, Trigger.STATUS_AVAILABLE),
        (StationState.CHARGING, Trigger.STATUS_CHARGING),
    }
    return (state, trigger) in idempotent


def allowed_transitions() -> list[tuple[StationState, Trigger, StationState]]:
    out = [(src, trg, dst) for (src, trg), dst in _T.items()]
    for s in _UNIVERSAL_TO_DISCONNECTED:
        out.append((s, Trigger.WS_CLOSE, StationState.DISCONNECTED))
    for s in _UNIVERSAL_TO_QUARANTINE:
        out.append((s, Trigger.QUARANTINE_SET, StationState.QUARANTINED))
    out.append((StationState.QUARANTINED, Trigger.QUARANTINE_CLEARED, StationState.AVAILABLE))
    return out
