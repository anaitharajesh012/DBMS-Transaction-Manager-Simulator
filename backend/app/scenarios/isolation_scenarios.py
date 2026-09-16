"""
isolation_scenarios.py - Reproducible Isolation Level Anomaly Scenarios.

Provides step-by-step simulations of classic concurrency anomalies:
1. Dirty Read: T2 reads uncommitted write of T1; T1 then aborts.
2. Non-Repeatable Read (Fuzzy Read): T1 reads A; T2 modifies A and commits; T1 reads A again with different value.
3. Lost Update: T1 and T2 both read A, calculate increments, and write back, overwriting one another.
4. Phantom Read: T1 reads a set of records; T2 inserts a new record; T1 reads again and discovers the phantom record.

Each scenario can be executed under:
- READ_UNCOMMITTED
- READ_COMMITTED
- REPEATABLE_READ
- SERIALIZABLE

Returns chronological step-by-step timeline and whether the anomaly occurred or was prevented.
"""

from typing import Any, Dict, List


def run_dirty_read_scenario(isolation_level: str) -> Dict[str, Any]:
    """
    Dirty Read:
    T1: updates A from 100 to 500
    T2: reads A
    T1: aborts (rolls back A to 100)
    Result:
      - Read Uncommitted: T2 read 500 (Dirty Read occurred!)
      - Read Committed / Repeatable Read / Serializable: T2 reads 100 (Prevented!)
    """
    level = isolation_level.upper()
    initial_state = {"A": 100}

    timeline = [
        {"step": 1, "txn": "T1", "action": "BEGIN", "detail": "Transaction T1 begins"},
        {"step": 2, "txn": "T2", "action": "BEGIN", "detail": "Transaction T2 begins"},
        {"step": 3, "txn": "T1", "action": "WRITE A = 500", "detail": "T1 updates A to 500 (uncommitted in memory)"},
    ]

    if level == "READ_UNCOMMITTED":
        timeline.append({
            "step": 4, "txn": "T2", "action": "READ A -> 500",
            "detail": "DIRTY READ! T2 reads uncommitted value 500 written by T1",
            "anomaly": True,
        })
        timeline.append({"step": 5, "txn": "T1", "action": "ABORT", "detail": "T1 aborts and rolls back A to 100"})
        timeline.append({"step": 6, "txn": "T2", "action": "COMMIT", "detail": "T2 commits with corrupt dirty data"})
        return {
            "anomaly_name": "Dirty Read",
            "isolation_level": level,
            "anomaly_occurred": True,
            "explanation": "At READ UNCOMMITTED, T2 read uncommitted dirty modifications of T1. When T1 subsequently aborted, T2 was left holding phantom data that never formally existed.",
            "initial_state": initial_state,
            "final_state": {"A": 100},
            "timeline": timeline,
            "t2_read_value": 500,
        }
    else:
        # Read Committed and higher
        timeline.append({
            "step": 4, "txn": "T2", "action": "READ A -> 100",
            "detail": "PREVENTED: T2 is blocked or reads committed snapshot version (100). Dirty read prevented!",
            "anomaly": False,
        })
        timeline.append({"step": 5, "txn": "T1", "action": "ABORT", "detail": "T1 aborts and rolls back"})
        timeline.append({"step": 6, "txn": "T2", "action": "COMMIT", "detail": "T2 commits cleanly"})
        return {
            "anomaly_name": "Dirty Read",
            "isolation_level": level,
            "anomaly_occurred": False,
            "explanation": f"At {level}, dirty reads are strictly prohibited. T2 only sees committed data or waits for exclusive lock release.",
            "initial_state": initial_state,
            "final_state": {"A": 100},
            "timeline": timeline,
            "t2_read_value": 100,
        }


def run_non_repeatable_read_scenario(isolation_level: str) -> Dict[str, Any]:
    """
    Non-Repeatable Read:
    T1: reads A (100)
    T2: updates A to 250 and commits
    T1: reads A again
    Result:
      - Read Uncommitted / Read Committed: T1 reads 100 first, then 250 (Non-Repeatable Read occurred!)
      - Repeatable Read / Serializable: T1 reads 100 both times (Prevented!)
    """
    level = isolation_level.upper()
    initial_state = {"A": 100}

    timeline = [
        {"step": 1, "txn": "T1", "action": "BEGIN", "detail": "Transaction T1 begins"},
        {"step": 2, "txn": "T1", "action": "READ A -> 100", "detail": "T1 reads A for the first time: got 100"},
        {"step": 3, "txn": "T2", "action": "BEGIN", "detail": "Transaction T2 begins"},
        {"step": 4, "txn": "T2", "action": "WRITE A = 250", "detail": "T2 updates A to 250"},
        {"step": 5, "txn": "T2", "action": "COMMIT", "detail": "T2 commits change"},
    ]

    if level in ("READ_UNCOMMITTED", "READ_COMMITTED"):
        timeline.append({
            "step": 6, "txn": "T1", "action": "READ A -> 250",
            "detail": "NON-REPEATABLE READ! T1 re-reads A and observes 250 instead of original 100 within the same transaction!",
            "anomaly": True,
        })
        timeline.append({"step": 7, "txn": "T1", "action": "COMMIT", "detail": "T1 commits"})
        return {
            "anomaly_name": "Non-Repeatable Read (Fuzzy Read)",
            "isolation_level": level,
            "anomaly_occurred": True,
            "explanation": f"At {level}, shared locks are released immediately after read operations rather than held until commit. T2 was able to update A concurrently.",
            "initial_state": initial_state,
            "final_state": {"A": 250},
            "timeline": timeline,
            "first_read": 100,
            "second_read": 250,
        }
    else:
        # Repeatable Read & Serializable
        timeline.append({
            "step": 6, "txn": "T1", "action": "READ A -> 100",
            "detail": "PREVENTED: T1 re-reads A and observes identical 100 (guaranteed repeatable via snapshot or held S-lock).",
            "anomaly": False,
        })
        timeline.append({"step": 7, "txn": "T1", "action": "COMMIT", "detail": "T1 commits"})
        return {
            "anomaly_name": "Non-Repeatable Read (Fuzzy Read)",
            "isolation_level": level,
            "anomaly_occurred": False,
            "explanation": f"At {level}, repeatable reads are guaranteed: transactions see the snapshot version from their start timestamp or hold S-locks until commit.",
            "initial_state": initial_state,
            "final_state": {"A": 250},
            "timeline": timeline,
            "first_read": 100,
            "second_read": 100,
        }


def run_lost_update_scenario(isolation_level: str) -> Dict[str, Any]:
    """
    Lost Update:
    T1 reads A (100)
    T2 reads A (100)
    T1 calculates 100 + 50 = 150, writes A = 150
    T2 calculates 100 + 30 = 130, writes A = 130 (overwrites T1's update!)
    Expected final state if serial: 100 + 50 + 30 = 180.
    """
    level = isolation_level.upper()
    initial_state = {"A": 100}

    timeline = [
        {"step": 1, "txn": "T1", "action": "READ A -> 100", "detail": "T1 reads balance: 100"},
        {"step": 2, "txn": "T2", "action": "READ A -> 100", "detail": "T2 reads balance: 100"},
        {"step": 3, "txn": "T1", "action": "WRITE A = 150", "detail": "T1 deposits 50 (100 + 50 = 150)"},
        {"step": 4, "txn": "T1", "action": "COMMIT", "detail": "T1 commits"},
    ]

    if level in ("READ_UNCOMMITTED", "READ_COMMITTED"):
        timeline.append({
            "step": 5, "txn": "T2", "action": "WRITE A = 130",
            "detail": "LOST UPDATE! T2 overwrites A with 130 (100 + 30), completely erasing T1's 50 deposit!",
            "anomaly": True,
        })
        timeline.append({"step": 6, "txn": "T2", "action": "COMMIT", "detail": "T2 commits"})
        return {
            "anomaly_name": "Lost Update",
            "isolation_level": level,
            "anomaly_occurred": True,
            "explanation": f"At {level}, uncoordinated concurrent read-modify-write sequences overwrite each other, causing silent loss of committed updates.",
            "initial_state": initial_state,
            "final_state": {"A": 130},
            "expected_serial_state": {"A": 180},
            "timeline": timeline,
        }
    else:
        timeline.append({
            "step": 5, "txn": "T2", "action": "CONFLICT DETECTED / RETRY",
            "detail": "PREVENTED: T2 detects write-write conflict or was serialized behind T1. T2 re-reads A=150 and writes 180.",
            "anomaly": False,
        })
        timeline.append({"step": 6, "txn": "T2", "action": "WRITE A = 180 & COMMIT", "detail": "T2 commits with correct aggregated balance 180"})
        return {
            "anomaly_name": "Lost Update",
            "isolation_level": level,
            "anomaly_occurred": False,
            "explanation": f"At {level}, write-write conflicts force abort/serialization, preventing lost updates and preserving cumulative consistency.",
            "initial_state": initial_state,
            "final_state": {"A": 180},
            "expected_serial_state": {"A": 180},
            "timeline": timeline,
        }


def run_phantom_read_scenario(isolation_level: str) -> Dict[str, Any]:
    """
    Phantom Read:
    T1 queries count of active accounts (initially 2: A and B)
    T2 inserts new account C
    T1 re-queries count of active accounts
    Result:
      - At weak levels: count changes from 2 to 3 (Phantom!)
      - At Serializable: count remains 2 or T2 blocks until T1 completes.
    """
    level = isolation_level.upper()
    initial_state = {"A": 100, "B": 200}

    timeline = [
        {"step": 1, "txn": "T1", "action": "QUERY COUNT -> 2", "detail": "T1 counts accounts: [A, B] -> Count = 2"},
        {"step": 2, "txn": "T2", "action": "INSERT C = 300", "detail": "T2 creates new account C"},
        {"step": 3, "txn": "T2", "action": "COMMIT", "detail": "T2 commits new record C"},
    ]

    if level in ("READ_UNCOMMITTED", "READ_COMMITTED", "REPEATABLE_READ"):
        timeline.append({
            "step": 4, "txn": "T1", "action": "QUERY COUNT -> 3",
            "detail": "PHANTOM READ! T1 re-queries and discovers phantom account C! Count changed from 2 to 3.",
            "anomaly": True,
        })
        timeline.append({"step": 5, "txn": "T1", "action": "COMMIT", "detail": "T1 commits"})
        return {
            "anomaly_name": "Phantom Read",
            "isolation_level": level,
            "anomaly_occurred": True,
            "explanation": f"At {level}, row-level locks protect existing items but cannot prevent insertion of new rows matching predicate queries (requires predicate or serializable locking).",
            "initial_state": initial_state,
            "final_state": {"A": 100, "B": 200, "C": 300},
            "timeline": timeline,
        }
    else:
        timeline.append({
            "step": 4, "txn": "T1", "action": "QUERY COUNT -> 2",
            "detail": "PREVENTED: Under Serializable isolation, T1 is insulated from concurrent inserts. Count remains 2.",
            "anomaly": False,
        })
        timeline.append({"step": 5, "txn": "T1", "action": "COMMIT", "detail": "T1 commits"})
        return {
            "anomaly_name": "Phantom Read",
            "isolation_level": level,
            "anomaly_occurred": False,
            "explanation": "At SERIALIZABLE isolation, phantom reads are eliminated entirely via range/predicate protection or serial snapshot isolation.",
            "initial_state": initial_state,
            "final_state": {"A": 100, "B": 200, "C": 300},
            "timeline": timeline,
        }
