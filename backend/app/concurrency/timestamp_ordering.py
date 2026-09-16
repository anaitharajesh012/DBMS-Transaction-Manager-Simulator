"""
timestamp_ordering.py - Basic Timestamp Ordering Concurrency Control with Thomas Write Rule.

Rules:
1. Each transaction T has a unique timestamp TS(T).
2. Each data item X maintains:
   - R_TS(X): largest timestamp of any transaction that read X.
   - W_TS(X): largest timestamp of any transaction that wrote X.

Read Rule (T requests read on X):
  - If TS(T) < W_TS(X):
      T is reading an overwritten value; T must ABORT.
  - Else:
      Read permitted; R_TS(X) = max(R_TS(X), TS(T)).

Write Rule (T requests write on X):
  - If TS(T) < R_TS(X):
      Value was already read by a newer transaction; T must ABORT.
  - If TS(T) < W_TS(X):
      THOMAS WRITE RULE: An even newer transaction has already overwritten X.
      Instead of aborting, silently IGNORE this obsolete write and proceed!
  - Else:
      Write permitted; W_TS(X) = TS(T).
"""

import threading
from typing import Dict, Set
from app.concurrency.base import ConcurrencyProtocol


class TimestampOrdering(ConcurrencyProtocol):
    """
    Timestamp Ordering with Thomas Write Rule.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._txn_timestamps: Dict[str, float] = {}
        # Per-key timestamps
        self._r_ts: Dict[str, float] = {}
        self._w_ts: Dict[str, float] = {}
        # Track ignored writes per transaction: txn_id -> set of keys where write was ignored
        self._ignored_writes: Dict[str, Set[str]] = {}

    def begin(self, txn_id: str, timestamp: float) -> None:
        with self._lock:
            self._txn_timestamps[txn_id] = timestamp
            self._ignored_writes[txn_id] = set()

    def before_read(self, txn_id: str, key: str) -> bool:
        with self._lock:
            ts = self._txn_timestamps.get(txn_id)
            if ts is None:
                return False

            w_ts = self._w_ts.get(key, 0.0)
            if ts < w_ts:
                # Read too late: abort
                return False

            # Valid read: update R_TS
            self._r_ts[key] = max(self._r_ts.get(key, 0.0), ts)
            return True

    def before_write(self, txn_id: str, key: str) -> bool:
        with self._lock:
            ts = self._txn_timestamps.get(txn_id)
            if ts is None:
                return False

            r_ts = self._r_ts.get(key, 0.0)
            if ts < r_ts:
                # Value was already read by a younger transaction: abort
                return False

            w_ts = self._w_ts.get(key, 0.0)
            if ts < w_ts:
                # Thomas Write Rule: obsolete write, ignore and do not abort!
                self._ignored_writes.setdefault(txn_id, set()).add(key)
                return True

            # Valid write: update W_TS
            self._w_ts[key] = ts
            # If it was previously marked ignored, discard that
            self._ignored_writes.get(txn_id, set()).discard(key)
            return True

    def is_write_ignored(self, txn_id: str, key: str) -> bool:
        with self._lock:
            return key in self._ignored_writes.get(txn_id, set())

    def on_commit(self, txn_id: str) -> bool:
        with self._lock:
            self._txn_timestamps.pop(txn_id, None)
            self._ignored_writes.pop(txn_id, None)
            return True

    def on_abort(self, txn_id: str) -> None:
        with self._lock:
            self._txn_timestamps.pop(txn_id, None)
            self._ignored_writes.pop(txn_id, None)

    def get_key_timestamps(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            all_keys = set(self._r_ts.keys()).union(self._w_ts.keys())
            return {
                k: {
                    "r_ts": self._r_ts.get(k, 0.0),
                    "w_ts": self._w_ts.get(k, 0.0),
                }
                for k in all_keys
            }
