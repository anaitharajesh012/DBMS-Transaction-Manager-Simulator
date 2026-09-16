"""
test_protocols.py - Unit tests for all 4 Concurrency Control Protocols:
1. Strict 2PL
2. Timestamp Ordering (with Thomas Write Rule)
3. Optimistic Concurrency Control (OCC)
4. Multi-Version Concurrency Control (MVCC & Time-Travel)
"""

import time
import pytest
from app.lock_manager import LockManager
from app.concurrency.two_phase_locking import StrictTwoPhaseLocking
from app.concurrency.timestamp_ordering import TimestampOrdering
from app.concurrency.occ import OptimisticConcurrencyControl
from app.concurrency.mvcc import MultiVersionConcurrencyControl


# ==========================================
# 1. Strict 2PL Tests
# ==========================================
def test_strict_2pl_locks_and_shrinking():
    lm = LockManager()
    s2pl = StrictTwoPhaseLocking(lm)

    s2pl.begin("T1", 1.0)
    assert s2pl.before_read("T1", "A") is True
    assert s2pl.before_write("T1", "B") is True

    # Locks should be held
    held = lm.get_locks_held("T1")
    assert held["A"] == "S"
    assert held["B"] == "X"

    # Shrinking phase: on commit, all locks must be released
    s2pl.on_commit("T1")
    assert lm.get_locks_held("T1") == {}


# ==========================================
# 2. Timestamp Ordering Tests
# ==========================================
def test_timestamp_ordering_normal_flow():
    to = TimestampOrdering()
    to.begin("T1", 10.0)
    to.begin("T2", 20.0)

    # T1 reads A
    assert to.before_read("T1", "A") is True
    # T2 writes A (TS(T2)=20 >= R_TS(A)=10)
    assert to.before_write("T2", "A") is True


def test_timestamp_ordering_read_too_late_aborts():
    to = TimestampOrdering()
    to.begin("T1", 10.0)
    to.begin("T2", 20.0)

    # T2 writes A first -> W_TS(A) becomes 20
    assert to.before_write("T2", "A") is True

    # T1 (TS=10) tries to read A -> TS(T1) < W_TS(A) -> Must ABORT
    assert to.before_read("T1", "A") is False


def test_timestamp_ordering_thomas_write_rule():
    to = TimestampOrdering()
    to.begin("T_late", 10.0)
    to.begin("T_early", 20.0)

    # T_early (TS=20) writes A -> W_TS(A) = 20
    assert to.before_write("T_early", "A") is True

    # T_late (TS=10) tries to write A -> TS < W_TS
    # Under Thomas Write Rule: write is IGNORED, but transaction does NOT abort!
    assert to.before_write("T_late", "A") is True
    assert to.is_write_ignored("T_late", "A") is True


# ==========================================
# 3. OCC Tests
# ==========================================
def test_occ_no_conflict_commits():
    occ = OptimisticConcurrencyControl()
    occ.begin("T1", 10.0)
    assert occ.before_read("T1", "A") is True
    occ.buffer_write("T1", "B", 100)

    # Validate and commit
    assert occ.on_commit("T1") is True
    assert occ.get_buffered_writes("T1") == {}  # cleared after commit


def test_occ_conflict_validation_aborts():
    occ = OptimisticConcurrencyControl()

    # T1 starts at t=1.0
    occ.begin("T1", 1.0)
    occ.before_read("T1", "A")

    # T2 starts at t=2.0, writes to A, and commits at t=3.0
    occ.begin("T2", 2.0)
    occ.buffer_write("T2", "A", 999)
    assert occ.on_commit("T2") is True

    # Now T1 tries to commit at t=4.0
    # Since T2 committed after T1's start and wrote to key A which T1 read:
    # Validation must FAIL and abort!
    assert occ.on_commit("T1") is False


# ==========================================
# 4. MVCC & Time-Travel Tests
# ==========================================
def test_mvcc_snapshot_isolation_and_time_travel():
    mvcc = MultiVersionConcurrencyControl()
    # Seed initial version at t=10.0
    mvcc.initialize_key("balance", 100, timestamp=10.0)

    # T1 starts at t=20.0, reads balance
    mvcc.begin("T1", 20.0)
    val_t1 = mvcc.read_value("T1", "balance", 100)
    assert val_t1 == 100

    # T2 starts at t=30.0, writes balance = 200, and commits at t=40.0
    mvcc.begin("T2", 30.0)
    assert mvcc.before_write("T2", "balance") is True
    mvcc.record_uncommitted_write("T2", "balance", 200)
    assert mvcc.on_commit("T2") is True

    # Even though T2 committed balance=200, T1 (started at t=20.0) STILL sees balance=100!
    # (Non-blocking Snapshot Isolation)
    val_t1_again = mvcc.read_value("T1", "balance", None)
    assert val_t1_again == 100

    # Verify time-travel queries
    # As of t=15 -> 100
    assert mvcc.get_version_at("balance", 15.0) == 100
    # As of current time -> 200
    assert mvcc.get_version_at("balance", time.time() + 1) == 200

    # Check version chain
    chain = mvcc.get_version_chain("balance")
    assert len(chain) == 2
    assert chain[0]["value"] == 100
    assert chain[1]["value"] == 200


def test_mvcc_first_committer_wins_write_conflict():
    mvcc = MultiVersionConcurrencyControl()
    mvcc.initialize_key("item", "v1", timestamp=10.0)

    # T1 starts at t=20
    mvcc.begin("T1", 20.0)

    # T2 starts at t=25, writes, and commits at t=30
    mvcc.begin("T2", 25.0)
    mvcc.record_uncommitted_write("T2", "item", "v2")
    assert mvcc.on_commit("T2") is True

    # T1 now attempts to write 'item'
    # Since a newer version was committed after T1 started (created_ts > 20.0),
    # T1 MUST ABORT (First-Committer-Wins rule prevents lost update)
    assert mvcc.before_write("T1", "item") is False
