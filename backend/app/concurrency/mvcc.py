"""
mvcc.py - Multi-Version Concurrency Control (MVCC) with Snapshot Isolation.

Key properties:
1. Version Chains: Every write creates a distinct version of a key tagged with
   created_ts and expired_ts.
2. Snapshot Isolation:
   - Readers see the version valid as of their transaction start timestamp:
       created_ts <= TS(T) < expired_ts
   - Readers never block writers; writers never block readers!
3. First-Committer-Wins Write-Write Conflict:
   - If T attempts to write a key where a newer version has already committed
     since T began (created_ts > TS(T)), T aborts to prevent lost updates.
4. Time-Travel Queries:
   - Exposes get_version_at(key, target_timestamp) and get_all_versions(key)
     enabling arbitrary point-in-time snapshot inspection!
"""

import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
from app.concurrency.base import ConcurrencyProtocol


@dataclass
class Version:
    txn_id: str
    created_ts: float
    expired_ts: float  # float('inf') if currently active head
    value: Any
    deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["expired_ts"] == float("inf"):
            d["expired_ts"] = None
        return d


class MultiVersionConcurrencyControl(ConcurrencyProtocol):
    """
    Multi-Version Concurrency Control implementing Snapshot Isolation and Time-Travel.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._txn_timestamps: Dict[str, float] = {}
        # Version chains: key -> list of Version objects in chronological order
        self._version_chains: Dict[str, List[Version]] = {}
        # Uncommitted versions per active transaction: txn_id -> {key: value}
        self._uncommitted_writes: Dict[str, Dict[str, Any]] = {}

    def begin(self, txn_id: str, timestamp: float) -> None:
        with self._lock:
            self._txn_timestamps[txn_id] = timestamp
            self._uncommitted_writes[txn_id] = {}

    def initialize_key(self, key: str, value: Any, timestamp: float = 0.0) -> None:
        """Initialize base version (e.g. from initial storage seed)."""
        with self._lock:
            if key not in self._version_chains:
                v = Version(
                    txn_id="SYSTEM_INIT",
                    created_ts=timestamp,
                    expired_ts=float("inf"),
                    value=value,
                )
                self._version_chains[key] = [v]

    def before_read(self, txn_id: str, key: str) -> bool:
        # In MVCC, reads are non-blocking and always allowed
        return True

    def before_write(self, txn_id: str, key: str) -> bool:
        """
        Snapshot Isolation write-write conflict check (First-Committer-Wins):
        If any version was created after txn_ts, abort to prevent lost updates.
        """
        with self._lock:
            txn_ts = self._txn_timestamps.get(txn_id)
            if txn_ts is None:
                return False

            chain = self._version_chains.get(key, [])
            if chain:
                # Check head of version chain
                head = chain[-1]
                if head.created_ts > txn_ts:
                    # A newer transaction already committed a change to this key!
                    return False

            return True

    def record_uncommitted_write(self, txn_id: str, key: str, value: Any) -> None:
        with self._lock:
            self._uncommitted_writes.setdefault(txn_id, {})[key] = value

    def read_value(self, txn_id: str, key: str, storage_val: Any) -> Any:
        """
        Read under Snapshot Isolation:
        1. If txn itself wrote uncommitted value, return it.
        2. Otherwise, find version where created_ts <= txn_ts < expired_ts.
        """
        with self._lock:
            # Own uncommitted write takes precedence
            own_writes = self._uncommitted_writes.get(txn_id, {})
            if key in own_writes:
                return own_writes[key]

            txn_ts = self._txn_timestamps.get(txn_id)
            if txn_ts is None:
                return storage_val

            return self.get_version_at(key, txn_ts)

    def get_version_at(self, key: str, target_ts: float) -> Optional[Any]:
        """
        Time-Travel Query:
        Return the value of key as of the specified historical logical timestamp.
        """
        with self._lock:
            chain = self._version_chains.get(key, [])
            for v in reversed(chain):
                if v.created_ts <= target_ts < v.expired_ts:
                    return None if v.deleted else v.value
            return None

    def get_version_chain(self, key: str) -> List[Dict[str, Any]]:
        """Return full history of versions for key (for time-travel visualization)."""
        with self._lock:
            return [v.to_dict() for v in self._version_chains.get(key, [])]

    def get_all_version_chains(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return all version chains for all keys."""
        with self._lock:
            return {
                k: [v.to_dict() for v in chain]
                for k, chain in self._version_chains.items()
            }

    def on_commit(self, txn_id: str) -> bool:
        """
        Finalize all uncommitted writes into the permanent version chain.
        """
        with self._lock:
            txn_ts = self._txn_timestamps.get(txn_id)
            if txn_ts is None:
                return False

            commit_ts = time.time()
            writes = self._uncommitted_writes.get(txn_id, {})

            for key, val in writes.items():
                chain = self._version_chains.setdefault(key, [])
                if chain:
                    # Expire current head
                    chain[-1].expired_ts = commit_ts

                new_version = Version(
                    txn_id=txn_id,
                    created_ts=commit_ts,
                    expired_ts=float("inf"),
                    value=val,
                )
                chain.append(new_version)

            self._cleanup(txn_id)
            return True

    def on_abort(self, txn_id: str) -> None:
        with self._lock:
            self._cleanup(txn_id)

    def _cleanup(self, txn_id: str) -> None:
        self._txn_timestamps.pop(txn_id, None)
        self._uncommitted_writes.pop(txn_id, None)
