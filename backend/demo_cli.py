"""
demo_cli.py - Standalone CLI Demonstration of DBMS Internals.

Runs full end-to-end demonstrations from the command line:
1. Concurrency Control: Strict 2PL concurrent transactions
2. Deadlock Detection & Resolution: cyclic wait-for graph, victim selection & retry
3. Timestamp Ordering & Thomas Write Rule
4. MVCC Time-Travel query
5. Simulated Crash & ARIES-Lite 3-Pass Recovery
"""

import os
import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.storage_engine import StorageEngine
from app.log_manager import LogManager
from app.transaction_manager import TransactionManager, TxnOp
from app.recovery_manager import RecoveryManager
from app.concurrency.timestamp_ordering import TimestampOrdering
from app.concurrency.mvcc import MultiVersionConcurrencyControl
from app.serializability import check_serializability


def print_banner(title: str):
    print("\n" + "=" * 70)
    print(f" >>> {title.upper()} <<<")
    print("=" * 70)


def demo_strict_2pl_and_deadlock():
    print_banner("1. Strict 2PL Concurrency Control & Deadlock Resolution")
    wal_path = "demo_wal.log"
    if os.path.exists(wal_path):
        os.remove(wal_path)

    storage = StorageEngine({"acc_A": 500, "acc_B": 500})
    log = LogManager(wal_path)

    deadlock_events = []
    def on_deadlock(event):
        deadlock_events.append(event)
        print(f"\n[ALERT] Deadlock Cycle Detected: {' -> '.join(event.cycle)}")
        print(f"[ALERT] Victim Chosen: {event.victim} (Policy: {event.policy})")

    tm = TransactionManager(
        storage_engine=storage,
        log_manager=log,
        protocol_type="2PL",
        deadlock_mode="detection",
        victim_policy="youngest",
    )
    tm.deadlock_detector.set_callback(on_deadlock)

    print("Initial storage:", storage.snapshot())
    print("Spawning T1 and T2 designed to conflict and create a deadlock cycle...")

    # T1: Write A, sleep, Write B
    ops_t1 = [
        TxnOp(op_type="WRITE", key="acc_A", value=400),
        TxnOp(op_type="SLEEP", duration=0.15),
        TxnOp(op_type="WRITE", key="acc_B", value=600),
    ]

    # T2: Write B, sleep, Write A
    ops_t2 = [
        TxnOp(op_type="WRITE", key="acc_B", value=450),
        TxnOp(op_type="SLEEP", duration=0.15),
        TxnOp(op_type="WRITE", key="acc_A", value=550),
    ]

    t1_id = tm.submit_transaction(ops_t1, txn_id="Txn_Transfer_1", max_retries=3)
    t2_id = tm.submit_transaction(ops_t2, txn_id="Txn_Transfer_2", max_retries=3)

    # Wait for completion
    for _ in range(30):
        t1_state = tm.get_transaction(t1_id)
        t2_state = tm.get_transaction(t2_id)
        if t1_state["status"] == "COMMITTED" and t2_state["status"] == "COMMITTED":
            break
        time.sleep(0.1)

    print("\nResulting Transaction States:")
    print(f" - {t1_id}: Status={tm.get_transaction(t1_id)['status']}, Retries={tm.get_transaction(t1_id)['retry_count']}")
    print(f" - {t2_id}: Status={tm.get_transaction(t2_id)['status']}, Retries={tm.get_transaction(t2_id)['retry_count']}")
    print("Final storage state:", storage.snapshot())
    tm.shutdown()
    if os.path.exists(wal_path):
        os.remove(wal_path)


def demo_thomas_write_rule():
    print_banner("2. Timestamp Ordering with Thomas Write Rule")
    to = TimestampOrdering()
    to.begin("T_older", 10.0)
    to.begin("T_younger", 20.0)

    print("Step 1: Younger transaction T_younger (TS=20) writes key 'item' -> updates W_TS to 20")
    to.before_write("T_younger", "item")

    print("Step 2: Older transaction T_older (TS=10) attempts to write key 'item'")
    allowed = to.before_write("T_older", "item")
    ignored = to.is_write_ignored("T_older", "item")

    print(f" -> Is write allowed? {allowed}")
    print(f" -> Is write ignored under Thomas Write Rule? {ignored}")
    print(" -> Thomas Write Rule preserves serializability without aborting the older transaction!")


def demo_mvcc_time_travel():
    print_banner("3. MVCC Snapshot Isolation & Time-Travel Queries")
    mvcc = MultiVersionConcurrencyControl()
    mvcc.initialize_key("config_param", "v1.0_initial", timestamp=10.0)

    print("Initial key 'config_param' created at t=10.0 with value 'v1.0_initial'")

    # Commit update at t=25
    mvcc.begin("T_updater", 25.0)
    mvcc.record_uncommitted_write("T_updater", "config_param", "v2.0_feature_release")
    mvcc.on_commit("T_updater")
    print("T_updater committed 'v2.0_feature_release'")

    # Perform time travel queries
    print("\n--- Time-Travel Inspection ---")
    val_at_15 = mvcc.get_version_at("config_param", 15.0)
    val_at_current = mvcc.get_version_at("config_param", time.time() + 10)
    print(f"Query AS OF t=15.0 (historical past): '{val_at_15}'")
    print(f"Query AS OF current head timestamp:  '{val_at_current}'")
    print("Full Version Chain:", mvcc.get_version_chain("config_param"))


def demo_crash_and_aries_recovery():
    print_banner("4. Chaos Crash Simulation & ARIES-Lite 3-Pass Recovery")
    crash_wal = "crash_demo.wal"
    if os.path.exists(crash_wal):
        os.remove(crash_wal)

    storage = StorageEngine({"A": 100, "B": 200})
    log = LogManager(crash_wal)

    print("Storage before crash:", storage.snapshot())

    # 1. Committed transaction
    log.log_begin("T_Committed")
    log.log_write("T_Committed", "A", 100, 999)
    storage.put("A", 999)
    log.log_commit("T_Committed")
    print("T_Committed wrote A=999 and logged COMMIT.")

    # 2. In-flight transaction active during sudden crash
    log.log_begin("T_InFlight_Loser")
    log.log_write("T_InFlight_Loser", "B", 200, 8888)
    storage.put("B", 8888)
    print("T_InFlight_Loser wrote dirty value B=8888 to storage and WAL.")
    print("Pre-crash memory state:", storage.snapshot())

    # 3. Simulate sudden system crash
    print("\n*** [SIMULATED CRASH] Power cut! In-memory state abruptly erased ***")
    storage.clear()
    print("Post-crash volatile storage:", storage.snapshot())

    # 4. ARIES 3-Pass Recovery
    print("\nInitiating RecoveryManager.recover()...")
    rm = RecoveryManager(log, storage)
    report = rm.recover()

    print("\n[PHASE 1: ANALYSIS PASS]")
    print(f" - Winner transactions: {report.winners}")
    print(f" - Loser transactions (to undo): {report.losers}")

    print("\n[PHASE 2: REDO PASS]")
    for r in report.redo_steps:
        print(f" - Redo LSN {r['lsn']}: {r['txn_id']} -> {r['key']} = {r['value_applied']}")

    print("\n[PHASE 3: UNDO PASS]")
    for u in report.undo_steps:
        print(f" - Undo LSN {u['undone_lsn']}: {u['txn_id']} -> {u['key']} rolled back to {u['restored_value']} (CLR LSN {u['clr_lsn']})")

    print("\nReconstructed Storage Snapshot:", storage.snapshot())
    assert storage.get("A") == 999, "Committed winner update must be preserved"
    assert storage.get("B") == 200, "Uncommitted dirty write must be cleanly undone to 200"
    print(">>> VERIFICATION PASSED: ACID Durability & Atomicity guaranteed! <<<")

    if os.path.exists(crash_wal):
        os.remove(crash_wal)


def demo_serializability():
    print_banner("5. Serializability Conflict Precedence Graph")
    sched_ok = "r1[x] w1[x] r2[x] w2[x] c1 c2"
    res_ok = check_serializability(sched_ok)
    print(f"Schedule: {sched_ok}")
    print(f" -> Is serializable? {res_ok.is_serializable}")
    print(f" -> Precedence Graph: {res_ok.precedence_graph}")
    print(f" -> Topological Sort: {res_ok.equivalent_serial_order}")

    sched_bad = "r1[x] w2[x] w1[x] c1 c2"
    res_bad = check_serializability(sched_bad)
    print(f"\nSchedule: {sched_bad}")
    print(f" -> Is serializable? {res_bad.is_serializable}")
    print(f" -> Cycles: {res_bad.cycles}")
    print(f" -> Explanation: {res_bad.explanation}")


if __name__ == "__main__":
    demo_strict_2pl_and_deadlock()
    demo_thomas_write_rule()
    demo_mvcc_time_travel()
    demo_crash_and_aries_recovery()
    demo_serializability()
    print_banner("ALL CLI DEMOS COMPLETED SUCCESSFULLY")
