from __future__ import annotations

import pytest

from ocpp_bench.csms import SessionStore


@pytest.mark.asyncio
async def test_duplicate_start_within_window_returns_same_id() -> None:
    s = SessionStore(duplicate_window_sec=10.0)
    txn1, dup1 = await s.open_or_dedupe("CP-1", 1, "RFID", 0, now=100.0)
    txn2, dup2 = await s.open_or_dedupe("CP-1", 1, "RFID", 0, now=105.0)
    assert dup1 is False
    assert dup2 is True
    assert txn1.transaction_id == txn2.transaction_id


@pytest.mark.asyncio
async def test_duplicate_outside_window_opens_new() -> None:
    s = SessionStore(duplicate_window_sec=10.0)
    txn1, dup1 = await s.open_or_dedupe("CP-1", 1, "RFID", 0, now=100.0)
    await s.close(txn1.transaction_id)
    txn2, dup2 = await s.open_or_dedupe("CP-1", 1, "RFID", 0, now=115.0)
    assert dup1 is False
    assert dup2 is False
    assert txn1.transaction_id != txn2.transaction_id


@pytest.mark.asyncio
async def test_different_id_tag_opens_new_even_within_window() -> None:
    s = SessionStore(duplicate_window_sec=10.0)
    txn1, _ = await s.open_or_dedupe("CP-1", 1, "RFID-A", 0, now=100.0)
    # Different tag within window still opens a fresh session — but the
    # connector already has an active txn so our caller would normally
    # reject; store-level we only dedupe when the id_tag matches.
    txn2, dup = await s.open_or_dedupe("CP-1", 1, "RFID-B", 0, now=102.0)
    assert dup is False
    assert txn1.transaction_id != txn2.transaction_id


@pytest.mark.asyncio
async def test_different_connector_is_independent() -> None:
    s = SessionStore()
    txn1, _ = await s.open_or_dedupe("CP-1", 1, "RFID", 0, now=100.0)
    txn2, dup = await s.open_or_dedupe("CP-1", 2, "RFID", 0, now=100.5)
    assert dup is False
    assert txn1.transaction_id != txn2.transaction_id
