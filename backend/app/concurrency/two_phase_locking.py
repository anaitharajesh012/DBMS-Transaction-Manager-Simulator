"""
two_phase_locking.py - Strict Two-Phase Locking (Strict 2PL).

Growing phase:
  Locks (Shared for reads, Exclusive for writes) are acquired dynamically as
  data items are accessed.
Shrinking phase:
  Strict rule: ALL locks held by the transaction are released simultaneously
  at the very end of the transaction (on commit or on abort).
  
Theoretical guarantees:
  1. Conflict Serializability: A transaction never acquires locks after releasing any.
  2. Avoid Cascading Aborts (ACA / Rigorous): Holding exclusive locks until commit
     ensures no other transaction can read uncommitted dirty data.
"""

from app.concurrency.base import ConcurrencyProtocol
from app.lock_manager import LockManager, LockMode


class StrictTwoPhaseLocking(ConcurrencyProtocol):
    """
    Strict 2PL concurrency control protocol delegating lock management to LockManager.
    """

    def __init__(self, lock_manager: LockManager):
        self.lock_manager = lock_manager

    def begin(self, txn_id: str, timestamp: float) -> None:
        self.lock_manager.register_txn(txn_id, timestamp)

    def before_read(self, txn_id: str, key: str) -> bool:
        """Acquire Shared (S) lock before reading key."""
        return self.lock_manager.acquire(txn_id, key, LockMode.SHARED)

    def before_write(self, txn_id: str, key: str) -> bool:
        """Acquire Exclusive (X) lock before writing key."""
        return self.lock_manager.acquire(txn_id, key, LockMode.EXCLUSIVE)

    def on_commit(self, txn_id: str) -> bool:
        """Strict shrinking phase: release all locks at commit."""
        self.lock_manager.release_all(txn_id)
        self.lock_manager.unregister_txn(txn_id)
        return True

    def on_abort(self, txn_id: str) -> None:
        """Strict shrinking phase: release all locks at abort."""
        self.lock_manager.release_all(txn_id)
        self.lock_manager.unregister_txn(txn_id)
