"""
test_integration.py - End-to-End Integration Tests.

Verifies:
1. Concurrent conflicting transactions through real TransactionManager maintain
   invariants (e.g. balance preservation A + B == 400) under multithreaded execution.
2. Deliberate deadlock is detected by background detector, resolved via victim abort & retry,
   and both transactions eventually commit cleanly.
3. Mid-execution crash simulation and ARIES recovery reconstructs consistent storage.
"""

import os
import tempfile
import time
import pytest
from app.log_manager import LogManager
from app.storage_engine import StorageEngine
from app.transaction_manager import TransactionManager, TxnOp, TxnStatus
from app.recovery_manager import RecoveryManager


@pytest.fixture
def tm_env():
    fd, path = tempfile.mkstemp(suffix=".wal")
    os.close(fd)
    storage = StorageEngine({"A": 200, "B": 200})
    log = LogManager(path)
    tm = TransactionManager(
        storage_engine=storage,
        log_manager=log,
        protocol_type="2PL",
        deadlock_mode="detection",
        victim_policy="youngest",
    )
    yield tm, storage, log, path
    tm.shutdown()
    if os.path.exists(path):
        os.remove(path)


def test_concurrent_bank_transfer_consistency(tm_env):
    """
    Two concurrent conflicting transactions transferring money between A and B.
    Total money must remain strictly invariant (400) regardless of thread interleaving.
    """
    tm, storage, log, path = tm_env

    # T1: Transfer 50 from A to B
    ops_t1 = [
        TxnOp(op_type="READ", key="A"),
        TxnOp(op_type="SLEEP", duration=0.03),
        TxnOp(op_type="WRITE", key="A", value=150),
        TxnOp(op_type="READ", key="B"),
        TxnOp(op_type="WRITE", key="B", value=250),
    ]

    # T2: Transfer 30 from B to A
    ops_t2 = [
        TxnOp(op_type="READ", key="B"),
        TxnOp(op_type="SLEEP", duration=0.03),
        TxnOp(op_type="WRITE", key="B", value=170),
        TxnOp(op_type="READ", key="A"),
        TxnOp(op_type="WRITE", key="A", value=230),
    ]

    tid1 = tm.submit_transaction(ops_t1, txn_id="Transfer1", max_retries=5)
    tid2 = tm.submit_transaction(ops_t2, txn_id="Transfer2", max_retries=5)

    # Wait for completion
    timeout = 10.0
    start = time.time()
    while time.time() - start < timeout:
        t1 = tm.get_transaction(tid1)
        t2 = tm.get_transaction(tid2)
        if t1["status"] in ("COMMITTED", "ABORTED") and t2["status"] in ("COMMITTED", "ABORTED"):
            break
        time.sleep(0.05)

    t1 = tm.get_transaction(tid1)
    t2 = tm.get_transaction(tid2)

    # At least one (or both) committed
    assert t1["status"] in ("COMMITTED", "ABORTED")
    assert t2["status"] in ("COMMITTED", "ABORTED")

    snap = storage.snapshot()
    total = snap["A"] + snap["B"]
    # Total invariant must be preserved
    assert total == 400


def test_deadlock_detection_and_automatic_retry(tm_env):
    """
    Deliberately forces a cyclic deadlock:
    T1 acquires A, then requests B.
    T2 acquires B, then requests A.
    Detector must detect cycle, abort victim, victim retries and succeeds.
    """
    tm, storage, log, path = tm_env

    # Force cross-lock deadlock
    ops_t1 = [
        TxnOp(op_type="WRITE", key="A", value=111),
        TxnOp(op_type="SLEEP", duration=0.1),
        TxnOp(op_type="WRITE", key="B", value=222),
    ]

    ops_t2 = [
        TxnOp(op_type="WRITE", key="B", value=333),
        TxnOp(op_type="SLEEP", duration=0.1),
        TxnOp(op_type="WRITE", key="A", value=444),
    ]

    tid1 = tm.submit_transaction(ops_t1, txn_id="Deadlock1", max_retries=3)
    tid2 = tm.submit_transaction(ops_t2, txn_id="Deadlock2", max_retries=3)

    # Wait for both to finish
    timeout = 10.0
    start = time.time()
    while time.time() - start < timeout:
        t1 = tm.get_transaction(tid1)
        t2 = tm.get_transaction(tid2)
        if t1["status"] == "COMMITTED" and t2["status"] == "COMMITTED":
            break
        time.sleep(0.05)

    t1 = tm.get_transaction(tid1)
    t2 = tm.get_transaction(tid2)

    # Both must eventually commit thanks to deadlock resolution + retry!
    assert t1["status"] == "COMMITTED"
    assert t2["status"] == "COMMITTED"

    # Deadlock history should record the event
    history = tm.deadlock_detector.get_history()
    assert len(history) >= 1
    assert "Deadlock1" in history[0]["cycle"] or "Deadlock2" in history[0]["cycle"]


def test_crash_and_aries_recovery_integration(tm_env):
    """
    Execute transaction that commits, then crash storage mid-flight during another transaction.
    Run ARIES recovery and assert only committed updates survive.
    """
    tm, storage, log, path = tm_env

    # 1. T_win commits
    ops_win = [
        TxnOp(op_type="WRITE", key="A", value=777),
    ]
    tid_win = tm.submit_transaction(ops_win, txn_id="WinnerTxn")

    time.sleep(0.2)
    assert tm.get_transaction(tid_win)["status"] == "COMMITTED"
    assert storage.get("A") == 777

    # 2. Directly write uncommitted dirty write into log and storage to simulate sudden crash
    log.log_begin("LoserCrashTxn")
    log.log_write("LoserCrashTxn", "B", 200, 9999)
    storage.put("B", 9999)

    # 3. Simulate sudden crash: shutdown and clear storage
    tm.shutdown()
    storage.clear()
    assert storage.snapshot() == {}

    # 4. Trigger recovery
    rm = RecoveryManager(log, storage)
    report = rm.recover()

    assert "WinnerTxn" in report.winners
    assert "LoserCrashTxn" in report.losers

    # Final state: A=777 (winner committed), B=200 (loser dirty write rolled back)
    recovered_snap = storage.snapshot()
    assert recovered_snap["A"] == 777
    assert recovered_snap["B"] == 200
