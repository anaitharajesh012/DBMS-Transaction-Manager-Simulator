"""
storage_engine.py - In-Memory Key-Value Storage Engine.

Acts as the raw "disk / page" storage layer for the transaction manager.
Contains zero transaction or concurrency control awareness.
Backed by an in-memory dictionary and guarded by a reentrant lock (RLock)
for safe multi-threaded reads, writes, deletions, and snapshots.
"""

import threading
from typing import Any, Dict, List, Optional


class StorageEngine:
    """
    Thread-safe raw key-value store.
    No transaction awareness; represents raw data storage.
    """

    def __init__(self, initial_data: Optional[Dict[str, Any]] = None):
        self._store: Dict[str, Any] = dict(initial_data) if initial_data else {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Retrieve value for a key, or None if not found."""
        with self._lock:
            return self._store.get(key)

    def put(self, key: str, value: Any) -> None:
        """Store or update a key-value pair."""
        with self._lock:
            self._store[key] = value

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if deleted, False if key did not exist."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def has(self, key: str) -> bool:
        """Check if key exists in the store."""
        with self._lock:
            return key in self._store

    def keys(self) -> List[str]:
        """Return a sorted copy of all existing keys."""
        with self._lock:
            return sorted(list(self._store.keys()))

    def snapshot(self) -> Dict[str, Any]:
        """
        Return an atomic, isolated point-in-time copy of the entire storage state.
        Modifying the returned dictionary has no effect on the underlying store.
        """
        with self._lock:
            return dict(self._store)

    def clear(self) -> None:
        """Clear all contents (used when simulating abrupt crash or resetting)."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __repr__(self) -> str:
        with self._lock:
            return f"StorageEngine(size={len(self._store)}, keys={list(self._store.keys())})"
