"""
occ.py - Optimistic Concurrency Control (OCC / Kung-Robinson).

Three Phases:
1. Read Phase:
   - Reads directly from storage (or own local workspace).
   - Writes are buffered entirely in a private local workspace.
   - Tracks ReadSet(T) and WriteSet(T).
2. Validation Phase:
   - At commit time, T is validated against all transactions Tc that committed
     after T began.
   - Validation Rule (Backward Validation):
     For each committed Tc where commit_ts(Tc) > start_ts(T):
       If WriteSet(Tc) ∩ ReadSet(T) != ∅:
         Validation fails -> T must ABORT and retry.
3. Write Phase:
   - Once validated, T atomically flushes its private workspace to WAL & storage.
"""

import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from app.concurrency.base import ConcurrencyProtocol


class CommittedTxnInfo:
    def __init__(self, txn_id: str, commit_ts: float, write_set: Set[str]):
        self.txn_id = txn_id
        self.commit_ts = commit_ts
        self.write_set = set(write_set)


class OptimisticConcurrencyControl(ConcurrencyProtocol):
    """
    Optimistic Concurrency Control with backward validation against committed transactions.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._start_timestamps: Dict[str, float] = {}
        self._read_sets: Dict[str, Set[str]] = {}
        self._write_sets: Dict[str, Set[str]] = {}
        # Local workspace: txn_id -> {key: buffered_value}
        self._local_workspaces: Dict[str, Dict[str, Any]] = {}
        # History of committed transactions for validation
        self._committed_history: List[CommittedTxnInfo] = []

    def begin(self, txn_id: str, timestamp: float) -> None:
        with self._lock:
            self._start_timestamps[txn_id] = timestamp
            self._read_sets[txn_id] = set()
            self._write_sets[txn_id] = set()
            self._local_workspaces[txn_id] = {}

    def before_read(self, txn_id: str, key: str) -> bool:
        with self._lock:
            if txn_id not in self._start_timestamps:
                return False
            self._read_sets.setdefault(txn_id, set()).add(key)
            return True

    def before_write(self, txn_id: str, key: str) -> bool:
        with self._lock:
            if txn_id not in self._start_timestamps:
                return False
            self._write_sets.setdefault(txn_id, set()).add(key)
            return True

    def buffer_write(self, txn_id: str, key: str, value: Any) -> None:
        """Buffer write into private workspace."""
        with self._lock:
            self._local_workspaces.setdefault(txn_id, {})[key] = value
            self._write_sets.setdefault(txn_id, set()).add(key)

    def read_value(self, txn_id: str, key: str, storage_val: Any) -> Any:
        """Read from local workspace if previously written in this transaction, else storage."""
        with self._lock:
            ws = self._local_workspaces.get(txn_id, {})
            if key in ws:
                return ws[key]
            return storage_val

    def get_buffered_writes(self, txn_id: str) -> Dict[str, Any]:
        """Return private workspace to be flushed to WAL & storage upon successful validation."""
        with self._lock:
            return dict(self._local_workspaces.get(txn_id, {}))

    def on_commit(self, txn_id: str) -> bool:
        """
        Validation Phase + Write Phase.
        Validates ReadSet(txn_id) against WriteSet(Tc) of concurrently committed transactions.
        """
        with self._lock:
            start_ts = self._start_timestamps.get(txn_id)
            if start_ts is None:
                return False

            read_set = self._read_sets.get(txn_id, set())
            write_set = self._write_sets.get(txn_id, set())

            # Backward validation: check all transactions committed after our start_ts
            for committed_txn in self._committed_history:
                if committed_txn.commit_ts > start_ts:
                    conflict = read_set.intersection(committed_txn.write_set)
                    if conflict:
                        # Validation failed: conflict detected!
                        self._cleanup(txn_id)
                        return False

            # Validation passed! Record this commit in history
            commit_ts = time.time()
            self._committed_history.append(
                CommittedTxnInfo(txn_id=txn_id, commit_ts=commit_ts, write_set=write_set)
            )

            # Keep history bounded (last 1000 transactions)
            if len(self._committed_history) > 1000:
                self._committed_history = self._committed_history[-500:]

            self._cleanup(txn_id)
            return True

    def on_abort(self, txn_id: str) -> None:
        with self._lock:
            self._cleanup(txn_id)

    def _cleanup(self, txn_id: str) -> None:
        self._start_timestamps.pop(txn_id, None)
        self._read_sets.pop(txn_id, None)
        self._write_sets.pop(txn_id, None)
        self._local_workspaces.pop(txn_id, None)
