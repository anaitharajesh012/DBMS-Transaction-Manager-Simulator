"""
test_lock_manager.py - Unit tests for LockManager.
"""

import threading
import time
import pytest
from app.lock_manager import LockManager, LockMode


def test_shared_locks_compatible():
    lm = LockManager()
    assert lm.acquire("T1", "A", LockMode.SHARED) is True
    assert lm.acquire("T2", "A", LockMode.SHARED) is True
    assert lm.acquire("T3", "A", LockMode.SHARED) is True

    locks = lm.get_all_locks()
    assert len(locks) == 1
    holders = {h["txn_id"] for h in locks[0]["holders"]}
    assert holders == {"T1", "T2", "T3"}


def test_exclusive_lock_incompatibility():
    lm = LockManager()
    assert lm.acquire("T1", "A", LockMode.EXCLUSIVE) is True

    # T2 should fail with timeout when requesting S or X
    t2_acquired = False

    def try_acquire():
        nonlocal t2_acquired
        t2_acquired = lm.acquire("T2", "A", LockMode.SHARED, timeout=0.1)

    t = threading.Thread(target=try_acquire)
    t.start()
    time.sleep(0.02)

    # Wait-for graph should show T2 waiting on T1
    wf = lm.get_wait_for_graph()
    assert "T2" in wf
    assert "T1" in wf["T2"]

    t.join()
    assert t2_acquired is False


def test_lock_upgrade():
    lm = LockManager()
    assert lm.acquire("T1", "A", LockMode.SHARED) is True
    # Sole holder upgrading to EXCLUSIVE should succeed
    assert lm.acquire("T1", "A", LockMode.EXCLUSIVE) is True
    assert lm.get_locks_held("T1")["A"] == LockMode.EXCLUSIVE


def test_release_all_unblocks_waiter():
    lm = LockManager()
    lm.acquire("T1", "A", LockMode.EXCLUSIVE)

    t2_result = [False]

    def waiter():
        t2_result[0] = lm.acquire("T2", "A", LockMode.EXCLUSIVE, timeout=1.0)

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.05)

    assert lm.get_wait_for_graph().get("T2") == ["T1"]

    # T1 releases all locks
    lm.release_all("T1")
    t.join()

    assert t2_result[0] is True
    assert "T2" not in lm.get_wait_for_graph()


def test_deadlock_prevention_wait_die():
    aborted_txns = []

    def on_abort(txn_id, reason):
        aborted_txns.append(txn_id)

    lm = LockManager(prevention_mode="wait_die", abort_callback=on_abort)
    # T_old has ts=1.0, T_young has ts=2.0
    lm.register_txn("T_old", 1.0)
    lm.register_txn("T_young", 2.0)

    # T_old holds lock on A
    lm.acquire("T_old", "A", LockMode.EXCLUSIVE)

    # T_young requests lock on A -> T_young is younger -> Wait-Die: T_young dies (aborts immediately)
    success = lm.acquire("T_young", "A", LockMode.EXCLUSIVE)
    assert success is False
    assert "T_young" in aborted_txns


def test_deadlock_prevention_wound_wait():
    wounded_txns = []

    def on_abort(txn_id, reason):
        wounded_txns.append(txn_id)

    lm = LockManager(prevention_mode="wound_wait", abort_callback=on_abort)
    lm.register_txn("T_old", 1.0)
    lm.register_txn("T_young", 2.0)

    # T_young holds lock on A
    lm.acquire("T_young", "A", LockMode.EXCLUSIVE)

    # T_old (older) requests lock on A -> Wound-Wait: T_old wounds younger holder T_young
    # We test with timeout so it returns when T_young doesn't immediately release in this test
    lm.acquire("T_old", "A", LockMode.EXCLUSIVE, timeout=0.05)
    assert "T_young" in wounded_txns
