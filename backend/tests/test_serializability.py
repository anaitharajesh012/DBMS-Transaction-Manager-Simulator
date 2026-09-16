"""
test_serializability.py - Unit tests for Serializability Precedence Graph and Checker.
"""

import pytest
from app.serializability import check_serializability, parse_schedule


def test_parse_schedule_various_formats():
    s1 = "r1[x] w2[x] r1[y] w1[x] c1 c2"
    ops1 = parse_schedule(s1)
    assert len(ops1) == 6
    assert ops1[0].op_type == "R" and ops1[0].txn_id == "T1" and ops1[0].key == "x"
    assert ops1[1].op_type == "W" and ops1[1].txn_id == "T2" and ops1[1].key == "x"

    s2 = "r1(A), w2(A), c1, c2"
    ops2 = parse_schedule(s2)
    assert len(ops2) == 4
    assert ops2[0].key == "A"


def test_serializable_schedule():
    # T1 reads and writes A, then T2 reads and writes A
    schedule = "r1[A] w1[A] r2[A] w2[A] c1 c2"
    result = check_serializability(schedule)
    assert result.is_serializable is True
    assert result.cycles == []
    assert result.equivalent_serial_order == ["T1", "T2"]
    assert result.precedence_graph["T1"] == ["T2"]
    assert result.precedence_graph["T2"] == []


def test_non_serializable_schedule_cycle():
    # T1 reads A before T2 writes A (edge T1 -> T2)
    # T2 writes A before T1 writes A (edge T2 -> T1)
    schedule = "r1[A] w2[A] w1[A] c1 c2"
    result = check_serializability(schedule)
    assert result.is_serializable is False
    assert len(result.cycles) > 0
    assert result.equivalent_serial_order is None
    # Verify conflict edges recorded
    conflicts = result.conflicts
    assert any(c["conflict_type"] == "RW" and c["from_txn"] == "T1" and c["to_txn"] == "T2" for c in conflicts)
    assert any(c["conflict_type"] == "WW" and c["from_txn"] == "T2" and c["to_txn"] == "T1" for c in conflicts)


def test_three_transaction_serializable():
    # T1 -> T2 -> T3
    schedule = "r1[x] w1[x] r2[x] w2[x] r3[x] w3[x] c1 c2 c3"
    result = check_serializability(schedule)
    assert result.is_serializable is True
    assert result.equivalent_serial_order == ["T1", "T2", "T3"]
