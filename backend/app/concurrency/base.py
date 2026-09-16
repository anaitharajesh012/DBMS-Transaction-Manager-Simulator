"""
base.py - Abstract Base Class for Concurrency Control Protocols.

Every protocol implements the identical interface:
- begin(txn_id, timestamp)
- before_read(txn_id, key) -> bool
- before_write(txn_id, key) -> bool
- on_commit(txn_id) -> bool
- on_abort(txn_id) -> None

This enables complete pluggability in TransactionManager via constructor injection.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ConcurrencyProtocol(ABC):
    """
    Abstract interface for pluggable concurrency control strategies.
    """

    @abstractmethod
    def begin(self, txn_id: str, timestamp: float) -> None:
        """Called when a transaction begins."""
        pass

    @abstractmethod
    def before_read(self, txn_id: str, key: str) -> bool:
        """
        Validate or acquire permissions before reading key.
        Returns True if read is allowed, False if transaction must abort.
        """
        pass

    @abstractmethod
    def before_write(self, txn_id: str, key: str) -> bool:
        """
        Validate or acquire permissions before writing key.
        Returns True if write is allowed, False if transaction must abort.
        """
        pass

    @abstractmethod
    def on_commit(self, txn_id: str) -> bool:
        """
        Final validation and release of resources on commit.
        Returns True if commit succeeds, False if aborted (e.g. in OCC validation).
        """
        pass

    @abstractmethod
    def on_abort(self, txn_id: str) -> None:
        """Release all resources, locks, or buffers upon transaction abort."""
        pass

    def read_value(self, txn_id: str, key: str, storage_val: Any) -> Any:
        """
        Protocol-specific value resolver (e.g., MVCC reads snapshot version,
        OCC reads from local workspace if previously written in same txn).
        Default behavior returns storage_val directly.
        """
        return storage_val

    def get_buffered_writes(self, txn_id: str) -> Dict[str, Any]:
        """
        Return any buffered writes that need to be flushed at commit time
        (primarily for OCC). Default is empty dict.
        """
        return {}

    def is_write_ignored(self, txn_id: str, key: str) -> bool:
        """
        Returns True if write should be ignored under Thomas Write Rule.
        Default is False.
        """
        return False
