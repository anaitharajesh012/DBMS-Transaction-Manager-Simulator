"""
test_deadlock.py - Unit tests for Deadlock Detection and Prevention.
"""

import pytest
from app.deadlock_detector import DeadlockDetector, find_cycles


def test_find_cycles_acyclic():
    graph = {
        "T1": ["T2"],
        "T2": ["T3"],
        "T3": [],
    }
    assert find_cycles(graph) == []


def test_find_cycles_2_node_cycle():
    # T1 -> T2 and T2 -> T1
    graph = {
        "T1": ["T2"],
        "T2": ["T1"],
    }
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert cycles[0] == ["T1", "T2", "T1"] or cycles[0] == ["T2", "T1", "T2"]


def test_find_cycles_3_node_cycle():
    # T1 -> T2 -> T3 -> T1
    graph = {
        "T1": ["T2"],
        "T2": ["T3"],
        "T3": ["T1"],
    }
    cycles = find_cycles(graph)
    assert len(cycles) == 1
    assert "T1" in cycles[0] and "T2" in cycles[0] and "T3" in cycles[0]


def test_victim_selection_youngest():
    # T1 (ts=100) -> T2 (ts=200) -> T1
    timestamps = {"T1": 100.0, "T2": 200.0}
    aborted = []

    detector = DeadlockDetector(
        get_wait_for_graph_fn=lambda: {"T1": ["T2"], "T2": ["T1"]},
        get_locks_held_fn=lambda t: {"A": "X"} if t == "T1" else {"B": "X"},
        get_txn_timestamp_fn=lambda t: timestamps.get(t, 0.0),
        abort_victim_fn=lambda v, r: aborted.append(v),
        policy="youngest",
    )

    event = detector.check_and_resolve()
    assert event is not None
    # Youngest is T2 (ts=200 > ts=100)
    assert event.victim == "T2"
    assert aborted == ["T2"]


def test_victim_selection_fewest_locks():
    # T1 holds 3 locks, T2 holds 1 lock
    # T1 (ts=200) -> T2 (ts=100) -> T1
    locks = {"T1": {"A": "X", "B": "X", "C": "X"}, "T2": {"D": "X"}}
    timestamps = {"T1": 200.0, "T2": 100.0}
    aborted = []

    detector = DeadlockDetector(
        get_wait_for_graph_fn=lambda: {"T1": ["T2"], "T2": ["T1"]},
        get_locks_held_fn=lambda t: locks.get(t, {}),
        get_txn_timestamp_fn=lambda t: timestamps.get(t, 0.0),
        abort_victim_fn=lambda v, r: aborted.append(v),
        policy="fewest_locks",
    )

    event = detector.check_and_resolve()
    assert event is not None
    # Fewest locks is T2 (1 lock < 3 locks)
    assert event.victim == "T2"
    assert aborted == ["T2"]
