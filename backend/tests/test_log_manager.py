"""
test_log_manager.py - Unit tests for LogManager.
"""

import os
import tempfile
import pytest
from app.log_manager import LogManager, LogRecord


@pytest.fixture
def temp_log():
    fd, path = tempfile.mkstemp(suffix=".wal")
    os.close(fd)
    lm = LogManager(path)
    yield lm, path
    if os.path.exists(path):
        os.remove(path)


def test_log_append_and_lsn(temp_log):
    lm, path = temp_log
    r1 = lm.log_begin("T1")
    r2 = lm.log_write("T1", "A", None, 100)
    r3 = lm.log_commit("T1")

    assert r1.lsn == 1
    assert r1.op_type == "BEGIN"
    assert r1.prev_lsn is None

    assert r2.lsn == 2
    assert r2.op_type == "WRITE"
    assert r2.key == "A"
    assert r2.old_value is None
    assert r2.new_value == 100
    assert r2.prev_lsn == 1

    assert r3.lsn == 3
    assert r3.op_type == "COMMIT"
    assert r3.prev_lsn == 2


def test_disk_persistence_and_replay(temp_log):
    lm, path = temp_log
    lm.log_begin("T1")
    lm.log_write("T1", "X", 10, 20)
    lm.log_begin("T2")
    lm.log_write("T2", "Y", None, 50)
    lm.log_commit("T1")

    # Create brand new LogManager pointing to same file
    lm_recovered = LogManager(path)
    records = lm_recovered.read_all()

    assert len(records) == 5
    assert [r.op_type for r in records] == ["BEGIN", "WRITE", "BEGIN", "WRITE", "COMMIT"]
    assert records[1].key == "X"
    assert records[3].key == "Y"

    # Verify continuing LSN from highest existing
    r_new = lm_recovered.log_commit("T2")
    assert r_new.lsn == 6


def test_prev_lsn_chains_per_transaction(temp_log):
    lm, path = temp_log
    r1 = lm.log_begin("T1")      # LSN 1
    r2 = lm.log_begin("T2")      # LSN 2
    r3 = lm.log_write("T1", "A", 0, 1)  # LSN 3, prev = 1
    r4 = lm.log_write("T2", "B", 0, 2)  # LSN 4, prev = 2
    r5 = lm.log_write("T1", "A", 1, 3)  # LSN 5, prev = 3
    r6 = lm.log_abort("T2")      # LSN 6, prev = 4

    assert r3.prev_lsn == 1
    assert r4.prev_lsn == 2
    assert r5.prev_lsn == 3
    assert r6.prev_lsn == 4
