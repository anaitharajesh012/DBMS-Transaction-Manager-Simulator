"""
test_storage_engine.py - Unit tests for StorageEngine.
"""

import threading
import pytest
from app.storage_engine import StorageEngine


def test_basic_crud():
    engine = StorageEngine({"A": 100, "B": 200})
    assert engine.get("A") == 100
    assert engine.get("B") == 200
    assert engine.get("C") is None

    engine.put("C", 300)
    assert engine.get("C") == 300
    assert engine.has("C") is True
    assert len(engine) == 3
    assert engine.keys() == ["A", "B", "C"]

    assert engine.delete("B") is True
    assert engine.has("B") is False
    assert engine.delete("B") is False
    assert engine.get("B") is None


def test_snapshot_isolation():
    engine = StorageEngine({"X": 10, "Y": 20})
    snap = engine.snapshot()
    assert snap == {"X": 10, "Y": 20}

    # Mutating engine should not alter snapshot
    engine.put("X", 999)
    engine.put("Z", 50)
    assert snap == {"X": 10, "Y": 20}
    assert engine.get("X") == 999

    # Mutating snapshot should not alter engine
    snap["Y"] = 888
    assert engine.get("Y") == 20


def test_multithreaded_concurrent_access():
    engine = StorageEngine({"counter": 0})
    num_threads = 10
    increments_per_thread = 100

    def worker():
        for _ in range(increments_per_thread):
            with engine._lock:
                val = engine.get("counter")
                engine.put("counter", val + 1)

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert engine.get("counter") == num_threads * increments_per_thread
