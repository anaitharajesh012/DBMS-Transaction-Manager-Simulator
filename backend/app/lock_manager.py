"""
lock_manager.py - Fine-Grained Shared and Exclusive Lock Manager with Wait-For Graph.

A pure resource-locking primitive independent of high-level transaction logic.
Supports:
1. Shared (S) and Exclusive (X) locks per key.
2. Lock upgrade (S -> X) when single holder.
3. Real-time Wait-For Graph maintenance (who is waiting on whom).
4. Deadlock prevention modes:
   - "none": standard blocking wait; deadlock resolved by external cycle detector.
   - "wound_wait": older transaction wounds (preempts/aborts) younger lock holder; younger waits.
   - "wait_die": older transaction waits; younger transaction dies (aborts immediately).
5. Thread synchronization using Python's threading.Condition.
"""

import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class LockMode(str, Enum):
    SHARED = "S"
    EXCLUSIVE = "X"


class LockRequest:
    def __init__(self, txn_id: str, mode: LockMode, timestamp: float):
        self.txn_id = txn_id
        self.mode = mode
        self.timestamp = timestamp
        self.granted = False
        self.aborted = False


class KeyLock:
    """Tracks state of locks on a single key."""

    def __init__(self, key: str):
        self.key = key
        # Dict of txn_id -> LockMode
        self.holders: Dict[str, LockMode] = {}
        # Queue of waiting LockRequests
        self.waiting: List[LockRequest] = []


class LockManager:
    """
    Granular lock manager managing S and X locks and tracking wait-for dependencies.
    """

    def __init__(
        self,
        prevention_mode: str = "none",  # "none", "wound_wait", "wait_die"
        abort_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.prevention_mode = prevention_mode.lower()
        self.abort_callback = abort_callback  # callback(txn_id, reason)
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._key_locks: Dict[str, KeyLock] = {}
        # Mapping: txn_id -> dict of {key: LockMode}
        self._txn_locks: Dict[str, Dict[str, LockMode]] = {}
        # Mapping: txn_id -> timestamp (for deadlock prevention comparison)
        self._txn_timestamps: Dict[str, float] = {}
        # Wait-for graph: waiting_txn -> set of holding_txns it is blocked by
        self._wait_for_graph: Dict[str, Set[str]] = {}

    def set_prevention_mode(self, mode: str) -> None:
        with self._lock:
            self.prevention_mode = mode.lower()

    def register_txn(self, txn_id: str, timestamp: float) -> None:
        with self._lock:
            self._txn_timestamps[txn_id] = timestamp
            if txn_id not in self._txn_locks:
                self._txn_locks[txn_id] = {}

    def unregister_txn(self, txn_id: str) -> None:
        with self._lock:
            self._txn_timestamps.pop(txn_id, None)

    def _is_compatible(self, key_lock: KeyLock, txn_id: str, requested_mode: LockMode) -> bool:
        """Check if lock request is immediately compatible with current holders."""
        if not key_lock.holders:
            return True

        if requested_mode == LockMode.SHARED:
            # S is compatible if all current holders hold S (or only txn_id holds)
            return all(
                mode == LockMode.SHARED or holder == txn_id
                for holder, mode in key_lock.holders.items()
            )

        if requested_mode == LockMode.EXCLUSIVE:
            # X is compatible only if txn_id is already the sole holder
            return list(key_lock.holders.keys()) == [txn_id]

        return False

    def acquire(
        self,
        txn_id: str,
        key: str,
        mode: LockMode = LockMode.SHARED,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Acquire lock on key in specified mode.
        Returns True if acquired.
        Returns False if aborted (by Wait-Die / Wound-Wait / deadlock victim) or timed out.
        """
        start_time = time.time()
        with self._cond:
            # If txn already holds the requested lock or a stronger lock
            current_hold = self._txn_locks.get(txn_id, {}).get(key)
            if current_hold == LockMode.EXCLUSIVE:
                return True
            if current_hold == LockMode.SHARED and mode == LockMode.SHARED:
                return True

            if key not in self._key_locks:
                self._key_locks[key] = KeyLock(key)
            kl = self._key_locks[key]

            txn_ts = self._txn_timestamps.get(txn_id, time.time())

            # Check if immediately grantable (and no prior waiters queued before it)
            if self._is_compatible(kl, txn_id, mode) and not kl.waiting:
                kl.holders[txn_id] = mode
                self._txn_locks.setdefault(txn_id, {})[key] = mode
                return True

            # If conflict exists, evaluate Deadlock Prevention mode
            conflicting_holders = [
                h for h in kl.holders.keys() if h != txn_id
            ]

            if self.prevention_mode == "wait_die":
                # Wait-Die: If T_req is older than ALL conflicting holders, T_req waits;
                # else (T_req is younger than at least one holder) T_req dies (aborts immediately).
                for holder in conflicting_holders:
                    holder_ts = self._txn_timestamps.get(holder, 0.0)
                    if txn_ts > holder_ts:
                        # Requestor is younger: DIE
                        if self.abort_callback:
                            self.abort_callback(txn_id, f"Wait-Die: {txn_id} (ts={txn_ts:.3f}) younger than holder {holder} (ts={holder_ts:.3f})")
                        return False

            elif self.prevention_mode == "wound_wait":
                # Wound-Wait: If T_req is older than holder, T_req wounds (aborts) holder;
                # if T_req is younger than holder, T_req waits.
                for holder in conflicting_holders:
                    holder_ts = self._txn_timestamps.get(holder, 0.0)
                    if txn_ts < holder_ts:
                        # Requestor is older: WOUND younger holder
                        if self.abort_callback:
                            self.abort_callback(holder, f"Wound-Wait: wounded by older {txn_id} (ts={txn_ts:.3f})")

            # Enqueue request
            req = LockRequest(txn_id, mode, txn_ts)
            kl.waiting.append(req)

            # Update wait-for graph
            self._wait_for_graph[txn_id] = set(conflicting_holders)

            try:
                while True:
                    if req.aborted:
                        return False

                    # Check if head of wait queue and compatible
                    if kl.waiting and kl.waiting[0] == req and self._is_compatible(kl, txn_id, mode):
                        kl.waiting.pop(0)
                        kl.holders[txn_id] = mode
                        self._txn_locks.setdefault(txn_id, {})[key] = mode
                        self._wait_for_graph.pop(txn_id, None)
                        return True

                    remaining_timeout = None
                    if timeout is not None:
                        elapsed = time.time() - start_time
                        remaining_timeout = timeout - elapsed
                        if remaining_timeout <= 0:
                            if req in kl.waiting:
                                kl.waiting.remove(req)
                            self._wait_for_graph.pop(txn_id, None)
                            return False

                    self._cond.wait(timeout=remaining_timeout)
            finally:
                if req in kl.waiting:
                    kl.waiting.remove(req)
                self._wait_for_graph.pop(txn_id, None)

    def abort_request(self, txn_id: str) -> bool:
        """Mark any pending lock request of txn_id as aborted and notify."""
        with self._cond:
            aborted_any = False
            for kl in self._key_locks.values():
                for req in kl.waiting:
                    if req.txn_id == txn_id:
                        req.aborted = True
                        aborted_any = True
            self._wait_for_graph.pop(txn_id, None)
            if aborted_any:
                self._cond.notify_all()
            return aborted_any

    def release(self, txn_id: str, key: str) -> bool:
        """Release lock held by txn_id on key."""
        with self._cond:
            if key not in self._key_locks:
                return False
            kl = self._key_locks[key]
            if txn_id in kl.holders:
                del kl.holders[txn_id]
                if txn_id in self._txn_locks and key in self._txn_locks[txn_id]:
                    del self._txn_locks[txn_id][key]

                # If no holders and no waiters, clean up key
                if not kl.holders and not kl.waiting:
                    del self._key_locks[key]

                # Recompute wait-for graph for remaining waiters
                self._update_wait_for_graph()
                self._cond.notify_all()
                return True
            return False

    def release_all(self, txn_id: str) -> List[str]:
        """Release all locks currently held by txn_id. Returns list of released keys."""
        with self._cond:
            held_keys = list(self._txn_locks.get(txn_id, {}).keys())
            for key in held_keys:
                self.release(txn_id, key)
            self._txn_locks.pop(txn_id, None)
            self._wait_for_graph.pop(txn_id, None)
            self._update_wait_for_graph()
            self._cond.notify_all()
            return held_keys

    def _update_wait_for_graph(self) -> None:
        """Recompute current wait-for dependencies across all keys."""
        new_graph: Dict[str, Set[str]] = {}
        for key, kl in self._key_locks.items():
            for req in kl.waiting:
                blockers = {h for h in kl.holders.keys() if h != req.txn_id}
                if blockers:
                    new_graph.setdefault(req.txn_id, set()).update(blockers)
        self._wait_for_graph = new_graph

    def get_wait_for_graph(self) -> Dict[str, List[str]]:
        """Return a snapshot copy of the wait-for graph: {txn_id: [blocked_by_txn_ids]}."""
        with self._lock:
            return {txn: sorted(list(blockers)) for txn, blockers in self._wait_for_graph.items()}

    def get_locks_held(self, txn_id: str) -> Dict[str, str]:
        """Return dict of {key: mode_str} for a specific transaction."""
        with self._lock:
            return {k: v.value for k, v in self._txn_locks.get(txn_id, {}).items()}

    def get_all_locks(self) -> List[Dict[str, Any]]:
        """Return all active locks and waiters for dashboard telemetry."""
        with self._lock:
            result = []
            for key, kl in self._key_locks.items():
                result.append({
                    "key": key,
                    "holders": [{"txn_id": h, "mode": m.value} for h, m in kl.holders.items()],
                    "waiters": [{"txn_id": w.txn_id, "mode": w.mode.value} for w in kl.waiting],
                })
            return result

    def clear(self) -> None:
        """Clear all locks and waiters."""
        with self._cond:
            self._key_locks.clear()
            self._txn_locks.clear()
            self._txn_timestamps.clear()
            self._wait_for_graph.clear()
            self._cond.notify_all()
