"""
test_recovery.py - Unit tests for ARIES-Lite 3-Pass Recovery Manager.
"""

import os
import tempfile
import pytest
from app.log_manager import LogManager
from app.storage_engine import StorageEngine
from app.recovery_manager import RecoveryManager


@pytest.fixture
def recovery_env():
    fd, path = tempfile.mkstemp(suffix=".wal")
    os.close(fd)
    lm = LogManager(path)
    se = StorageEngine({"B": 50})
    rm = RecoveryManager(lm, se)
    yield lm, se, rm, path
    if os.path.exists(path):
        os.remove(path)


def test_aries_three_pass_recovery(recovery_env):
    lm, se, rm, path = recovery_env

    # 1. T1 begins, writes A=100, commits
    lm.log_begin("T1")
    lm.log_write("T1", "A", None, 100)
    se.put("A", 100)
    lm.log_commit("T1")

    # 2. T2 begins, writes B=200 (old was 50), NEVER commits (simulated crash)
    lm.log_begin("T2")
    lm.log_write("T2", "B", 50, 200)
    se.put("B", 200)
    # Crash happens right here! T2 is in-flight.

    # 3. Simulate crash: clear in-memory storage completely
    se.clear()
    assert se.snapshot() == {}

    # 4. Run ARIES-lite recovery
    report = rm.recover()

    # Verify Analysis pass results
    assert report.winners == ["T1"]
    assert report.losers == ["T2"]

    # Verify Redo pass replayed both writes
    redo_keys = [s["key"] for s in report.redo_steps]
    assert "A" in redo_keys
    assert "B" in redo_keys

    # Verify Undo pass undid T2's write on B
    assert len(report.undo_steps) == 1
    assert report.undo_steps[0]["key"] == "B"
    assert report.undo_steps[0]["restored_value"] == 50

    # Verify CLR written
    assert len(report.clrs_written) == 1

    # Verify Final Storage state:
    # A should be 100 (committed winner)
    # B should be 50 (loser undone back to old_value)
    final_storage = se.snapshot()
    assert final_storage["A"] == 100
    assert final_storage["B"] == 50


def test_recovery_idempotence(recovery_env):
    """Running recovery twice in sequence must produce identical consistent state."""
    lm, se, rm, path = recovery_env

    lm.log_begin("T1")
    lm.log_write("T1", "X", 10, 99)
    lm.log_commit("T1")

    lm.log_begin("T2")
    lm.log_write("T2", "X", 99, 500)
    # In-flight crash for T2

    # First recovery
    report1 = rm.recover()
    state1 = se.snapshot()
    assert state1["X"] == 99

    # Second crash & recovery
    se.clear()
    report2 = rm.recover()
    state2 = se.snapshot()
    assert state2["X"] == 99
    assert state1 == state2
