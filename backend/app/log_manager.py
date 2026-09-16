"""
log_manager.py - Append-Only Write-Ahead Log (WAL) Manager.

Enforces the fundamental Write-Ahead Logging invariant:
Every update must be durably appended and flushed to the log file on disk
BEFORE the corresponding change is applied to in-memory storage (StorageEngine).

Each log record records:
- lsn: Monotonically increasing Log Sequence Number.
- txn_id: Identifier of the transaction making the change.
- op_type: Operation type ('BEGIN', 'WRITE', 'COMMIT', 'ABORT', 'CHECKPOINT', 'CLR').
- key: Affected data item key (or None for BEGIN/COMMIT/ABORT/CHECKPOINT).
- old_value: Previous value before this write (used during UNDO recovery).
- new_value: New value after this write (used during REDO recovery).
- prev_lsn: LSN of the previous record written by this transaction (ARIES backward chain).
- undo_next_lsn: For CLR (Compensation Log Record) records during ARIES undo pass.
- timestamp: Wall-clock epoch timestamp.
"""

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LogRecord:
    lsn: int
    txn_id: str
    op_type: str  # BEGIN, WRITE, COMMIT, ABORT, CHECKPOINT, CLR
    key: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None
    prev_lsn: Optional[int] = None
    undo_next_lsn: Optional[int] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogRecord":
        return cls(**data)


class LogManager:
    """
    Append-only, thread-safe Write-Ahead Log manager with disk persistence.
    """

    def __init__(self, log_filepath: str):
        self.log_filepath = os.path.abspath(log_filepath)
        self._lock = threading.RLock()
        self._next_lsn = 1
        self._last_lsn_per_txn: Dict[str, int] = {}
        self._in_memory_records: List[LogRecord] = []

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.log_filepath), exist_ok=True)

        # If existing log file exists, scan to recover highest LSN
        if os.path.exists(self.log_filepath):
            existing = self.read_all()
            if existing:
                self._in_memory_records = existing
                self._next_lsn = max(r.lsn for r in existing) + 1
                for r in existing:
                    self._last_lsn_per_txn[r.txn_id] = r.lsn

    def append(
        self,
        txn_id: str,
        op_type: str,
        key: Optional[str] = None,
        old_value: Optional[Any] = None,
        new_value: Optional[Any] = None,
        undo_next_lsn: Optional[int] = None,
    ) -> LogRecord:
        """
        Append a log record and synchronously flush it to disk.
        Returns the recorded LogRecord.
        """
        with self._lock:
            lsn = self._next_lsn
            self._next_lsn += 1
            prev_lsn = self._last_lsn_per_txn.get(txn_id)

            record = LogRecord(
                lsn=lsn,
                txn_id=txn_id,
                op_type=op_type.upper(),
                key=key,
                old_value=old_value,
                new_value=new_value,
                prev_lsn=prev_lsn,
                undo_next_lsn=undo_next_lsn,
                timestamp=time.time(),
            )

            # Update backward pointer for this transaction
            self._last_lsn_per_txn[txn_id] = lsn
            self._in_memory_records.append(record)

            # Write and flush to disk
            self._flush_record_to_disk(record)

            return record

    def _flush_record_to_disk(self, record: LogRecord) -> None:
        """Write single record to disk and physically sync."""
        line = json.dumps(record.to_dict()) + "\n"
        with open(self.log_filepath, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def log_begin(self, txn_id: str) -> LogRecord:
        return self.append(txn_id=txn_id, op_type="BEGIN")

    def log_write(
        self, txn_id: str, key: str, old_value: Any, new_value: Any
    ) -> LogRecord:
        """
        Strict WAL guarantee: Must be called and completed BEFORE the
        storage engine updates the key.
        """
        return self.append(
            txn_id=txn_id,
            op_type="WRITE",
            key=key,
            old_value=old_value,
            new_value=new_value,
        )

    def log_commit(self, txn_id: str) -> LogRecord:
        return self.append(txn_id=txn_id, op_type="COMMIT")

    def log_abort(self, txn_id: str) -> LogRecord:
        return self.append(txn_id=txn_id, op_type="ABORT")

    def log_clr(
        self, txn_id: str, key: str, undid_to_value: Any, undo_next_lsn: Optional[int]
    ) -> LogRecord:
        """
        Compensation Log Record: written during the Undo pass of recovery
        to ensure that abort/recovery actions are never undone again (idempotent recovery).
        """
        return self.append(
            txn_id=txn_id,
            op_type="CLR",
            key=key,
            new_value=undid_to_value,
            undo_next_lsn=undo_next_lsn,
        )

    def log_checkpoint(self, active_txn_ids: List[str]) -> LogRecord:
        """
        Checkpoint record containing the list of active transactions at checkpoint time.
        """
        return self.append(
            txn_id="SYSTEM_CHECKPOINT",
            op_type="CHECKPOINT",
            new_value=list(active_txn_ids),
        )

    def read_all(self) -> List[LogRecord]:
        """
        Read all log records from disk in chronological order.
        Used by RecoveryManager to replay the log.
        """
        with self._lock:
            if not os.path.exists(self.log_filepath):
                return []
            records: List[LogRecord] = []
            with open(self.log_filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            records.append(LogRecord.from_dict(data))
                        except Exception:
                            continue
            return records

    def get_in_memory_records(self) -> List[LogRecord]:
        """Return shallow copy of records in memory."""
        with self._lock:
            return list(self._in_memory_records)

    def clear(self) -> None:
        """Clear log file and in-memory state (for testing or reset)."""
        with self._lock:
            self._next_lsn = 1
            self._last_lsn_per_txn.clear()
            self._in_memory_records.clear()
            if os.path.exists(self.log_filepath):
                with open(self.log_filepath, "w", encoding="utf-8") as f:
                    f.truncate(0)
