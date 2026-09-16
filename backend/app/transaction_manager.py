"""
transaction_manager.py - Core Orchestrator of Transactions.

Coordinates:
- StorageEngine (raw in-memory data store)
- LogManager (append-only WAL with disk flush)
- LockManager (S/X locks and wait-for graph)
- ConcurrencyProtocol (Strict 2PL, Timestamp Ordering, OCC, MVCC)
- DeadlockDetector (Cycle detection & victim aborts)

Guarantees:
1. Strict WAL Invariant: log_write() is physically flushed to disk BEFORE storage_engine.put().
2. Proper Atomicity: on abort, all writes made by the transaction are rolled back in reverse
   order using recorded old_values before ABORT is logged.
3. Pluggable Protocols: Protocol can be swapped at instantiation or dynamically.
4. Auto-Retry: Transactions aborted due to deadlock or validation failure can automatically retry.
5. Real-Time Telemetry: Emits events on every state transition, lock change, and WAL append.
"""

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.concurrency.base import ConcurrencyProtocol
from app.concurrency.mvcc import MultiVersionConcurrencyControl
from app.concurrency.occ import OptimisticConcurrencyControl
from app.concurrency.timestamp_ordering import TimestampOrdering
from app.concurrency.two_phase_locking import StrictTwoPhaseLocking
from app.deadlock_detector import DeadlockDetector
from app.lock_manager import LockManager
from app.log_manager import LogManager, LogRecord
from app.storage_engine import StorageEngine


class TxnStatus(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"
    RETRYING = "RETRYING"


class IsolationLevel(str, Enum):
    READ_UNCOMMITTED = "READ_UNCOMMITTED"
    READ_COMMITTED = "READ_COMMITTED"
    REPEATABLE_READ = "REPEATABLE_READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass
class TxnOp:
    op_type: str  # "READ", "WRITE", "SLEEP"
    key: Optional[str] = None
    value: Optional[Any] = None
    duration: float = 0.0  # seconds to sleep (for simulating realistic concurrency)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "op_type": self.op_type,
            "key": self.key,
            "value": self.value,
            "duration": self.duration,
        }


@dataclass
class TransactionContext:
    txn_id: str
    operations: List[TxnOp]
    isolation_level: IsolationLevel = IsolationLevel.SERIALIZABLE
    status: TxnStatus = TxnStatus.NEW
    start_time: float = 0.0
    end_time: Optional[float] = None
    current_op_index: int = 0
    writes_made: List[tuple] = field(default_factory=list)  # (key, old_value, new_value)
    read_values: Dict[str, Any] = field(default_factory=dict)
    abort_reason: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "status": self.status.value,
            "isolation_level": self.isolation_level.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "current_op_index": self.current_op_index,
            "total_ops": len(self.operations),
            "operations": [op.to_dict() for op in self.operations],
            "read_values": self.read_values,
            "abort_reason": self.abort_reason,
            "retry_count": self.retry_count,
        }


class TransactionManager:
    """
    Central transaction orchestrator managing multithreaded transactions,
    enforcing WAL protocol, and routing operations through pluggable concurrency control.
    """

    def __init__(
        self,
        storage_engine: StorageEngine,
        log_manager: LogManager,
        protocol_type: str = "2PL",  # "2PL", "TO", "OCC", "MVCC"
        deadlock_mode: str = "detection",  # "detection", "prevention"
        prevention_scheme: str = "wound_wait",  # "wound_wait", "wait_die"
        victim_policy: str = "youngest",  # "youngest", "fewest_locks"
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.storage_engine = storage_engine
        self.log_manager = log_manager
        self.event_callback = event_callback  # cb(event_type, payload)

        self._lock = threading.RLock()
        self._txns: Dict[str, TransactionContext] = {}
        self._aborted_flags: Dict[str, str] = {}  # txn_id -> reason
        self._next_txn_num = 1
        self._logical_ts = 1.0

        # Initialize Lock Manager
        prev_mode = prevention_scheme if deadlock_mode == "prevention" else "none"
        self.lock_manager = LockManager(
            prevention_mode=prev_mode,
            abort_callback=self._on_prevention_abort,
        )

        # Initialize Concurrency Protocol
        self.protocol_type = protocol_type.upper()
        self.protocol: ConcurrencyProtocol = self._build_protocol(self.protocol_type)

        # Initialize Deadlock Detector
        self.deadlock_detector = DeadlockDetector(
            get_wait_for_graph_fn=self.lock_manager.get_wait_for_graph,
            get_locks_held_fn=self.lock_manager.get_locks_held,
            get_txn_timestamp_fn=self._get_txn_timestamp,
            abort_victim_fn=self.abort_transaction,
            policy=victim_policy,
            poll_interval=0.08,
        )

        if deadlock_mode == "detection":
            self.deadlock_detector.start()

    def _build_protocol(self, p_type: str) -> ConcurrencyProtocol:
        p_type = p_type.upper()
        if p_type == "2PL":
            return StrictTwoPhaseLocking(self.lock_manager)
        elif p_type == "TO":
            return TimestampOrdering()
        elif p_type == "OCC":
            return OptimisticConcurrencyControl()
        elif p_type == "MVCC":
            mvcc = MultiVersionConcurrencyControl()
            # Seed MVCC version chains from initial storage items
            for k in self.storage_engine.keys():
                mvcc.initialize_key(k, self.storage_engine.get(k), timestamp=0.0)
            return mvcc
        else:
            raise ValueError(f"Unknown concurrency protocol: {p_type}")

    def set_protocol(self, protocol_type: str) -> None:
        """Dynamically swap active concurrency control protocol."""
        with self._lock:
            self.protocol_type = protocol_type.upper()
            self.protocol = self._build_protocol(self.protocol_type)
            self._emit_event("protocol_changed", {"protocol": self.protocol_type})

    def set_deadlock_mode(
        self,
        mode: str,
        prevention_scheme: str = "wound_wait",
        victim_policy: str = "youngest",
    ) -> None:
        """Dynamically change deadlock resolution configuration."""
        with self._lock:
            if mode == "detection":
                self.lock_manager.set_prevention_mode("none")
                self.deadlock_detector.set_policy(victim_policy)
                self.deadlock_detector.start()
            else:
                self.deadlock_detector.stop()
                self.lock_manager.set_prevention_mode(prevention_scheme)

            self._emit_event("deadlock_mode_changed", {
                "mode": mode,
                "prevention_scheme": prevention_scheme,
                "victim_policy": victim_policy,
            })

    def _on_prevention_abort(self, txn_id: str, reason: str) -> None:
        self.abort_transaction(txn_id, reason)

    def _get_txn_timestamp(self, txn_id: str) -> float:
        with self._lock:
            ctx = self._txns.get(txn_id)
            return ctx.start_time if ctx else 0.0

    def _emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        if self.event_callback:
            try:
                self.event_callback(event_type, payload)
            except Exception:
                pass

    def generate_txn_id(self) -> str:
        with self._lock:
            tid = f"T{self._next_txn_num}"
            self._next_txn_num += 1
            return tid

    def submit_transaction(
        self,
        operations: List[TxnOp],
        txn_id: Optional[str] = None,
        isolation_level: IsolationLevel = IsolationLevel.SERIALIZABLE,
        max_retries: int = 3,
        auto_start: bool = True,
    ) -> str:
        """
        Submit a new transaction for execution.
        Returns the assigned txn_id.
        """
        with self._lock:
            if not txn_id:
                txn_id = self.generate_txn_id()

            ctx = TransactionContext(
                txn_id=txn_id,
                operations=operations,
                isolation_level=isolation_level,
                status=TxnStatus.NEW,
                max_retries=max_retries,
            )
            self._txns[txn_id] = ctx
            self._emit_event("txn_submitted", ctx.to_dict())

        if auto_start:
            self._start_txn_thread(ctx)

        return txn_id

    def _start_txn_thread(self, ctx: TransactionContext) -> None:
        t = threading.Thread(
            target=self._execute_transaction,
            args=(ctx,),
            name=f"TxnThread-{ctx.txn_id}",
            daemon=True,
        )
        ctx.thread = t
        t.start()

    def abort_transaction(self, txn_id: str, reason: str) -> None:
        """Externally signal a transaction to abort (e.g. from deadlock detector)."""
        with self._lock:
            self._aborted_flags[txn_id] = reason
            ctx = self._txns.get(txn_id)
            if ctx and ctx.status in (TxnStatus.NEW, TxnStatus.RUNNING, TxnStatus.WAITING):
                ctx.abort_reason = reason
        # Wake up any blocked lock condition
        self.lock_manager.abort_request(txn_id)

    def _execute_transaction(self, ctx: TransactionContext) -> None:
        txn_id = ctx.txn_id

        while True:
            # Setup run
            with self._lock:
                self._logical_ts += 1.0
                ctx.start_time = self._logical_ts
                ctx.status = TxnStatus.RUNNING
                ctx.current_op_index = 0
                ctx.writes_made.clear()
                ctx.read_values.clear()
                ctx.abort_reason = None
                self._aborted_flags.pop(txn_id, None)

            self._emit_event("txn_status", ctx.to_dict())

            # 1. Log BEGIN in WAL
            self.log_manager.log_begin(txn_id)
            self._emit_event("wal_append", {"op": "BEGIN", "txn_id": txn_id})

            # 2. Inform concurrency protocol
            self.protocol.begin(txn_id, ctx.start_time)

            aborted = False
            abort_reason = None

            # 3. Execute operations sequentially
            for idx, op in enumerate(ctx.operations):
                with self._lock:
                    ctx.current_op_index = idx

                # Check if externally aborted (e.g. deadlock victim)
                if txn_id in self._aborted_flags:
                    aborted = True
                    abort_reason = self._aborted_flags[txn_id]
                    break

                if op.duration > 0:
                    time.sleep(op.duration)

                if op.op_type.upper() == "SLEEP":
                    continue

                elif op.op_type.upper() == "READ":
                    key = op.key
                    # Check with protocol
                    allowed = self.protocol.before_read(txn_id, key)
                    if not allowed or txn_id in self._aborted_flags:
                        aborted = True
                        abort_reason = self._aborted_flags.get(txn_id, f"Read conflict on {key}")
                        break

                    # Read value according to protocol
                    storage_val = self.storage_engine.get(key)
                    val = self.protocol.read_value(txn_id, key, storage_val)
                    ctx.read_values[key] = val
                    self._emit_event("txn_op", {
                        "txn_id": txn_id,
                        "op": "READ",
                        "key": key,
                        "value": val,
                        "index": idx,
                    })

                elif op.op_type.upper() == "WRITE":
                    key = op.key
                    new_val = op.value

                    # Check with protocol
                    allowed = self.protocol.before_write(txn_id, key)
                    if not allowed or txn_id in self._aborted_flags:
                        aborted = True
                        abort_reason = self._aborted_flags.get(txn_id, f"Write conflict on {key}")
                        break

                    # Check Thomas Write Rule
                    if self.protocol.is_write_ignored(txn_id, key):
                        # Obsolete write skipped per Thomas Write Rule
                        self._emit_event("txn_op", {
                            "txn_id": txn_id,
                            "op": "WRITE_IGNORED (Thomas Write Rule)",
                            "key": key,
                            "value": new_val,
                            "index": idx,
                        })
                        continue

                    old_val = self.storage_engine.get(key)

                    if isinstance(self.protocol, OptimisticConcurrencyControl):
                        # OCC buffers write in private workspace; doesn't write to storage or WAL yet
                        self.protocol.buffer_write(txn_id, key, new_val)
                        ctx.writes_made.append((key, old_val, new_val))
                    elif isinstance(self.protocol, MultiVersionConcurrencyControl):
                        self.protocol.record_uncommitted_write(txn_id, key, new_val)
                        # WAL write logged BEFORE storage update
                        self.log_manager.log_write(txn_id, key, old_val, new_val)
                        self.storage_engine.put(key, new_val)
                        ctx.writes_made.append((key, old_val, new_val))
                        self._emit_event("wal_append", {"op": "WRITE", "txn_id": txn_id, "key": key, "val": new_val})
                    else:
                        # Strict 2PL and Timestamp Ordering:
                        # STRICT WAL INVARIANT: write to log FIRST, then update storage
                        self.log_manager.log_write(txn_id, key, old_val, new_val)
                        self.storage_engine.put(key, new_val)
                        ctx.writes_made.append((key, old_val, new_val))
                        self._emit_event("wal_append", {"op": "WRITE", "txn_id": txn_id, "key": key, "val": new_val})

                    self._emit_event("txn_op", {
                        "txn_id": txn_id,
                        "op": "WRITE",
                        "key": key,
                        "value": new_val,
                        "index": idx,
                    })

            # Check if aborted before commit
            if not aborted and txn_id in self._aborted_flags:
                aborted = True
                abort_reason = self._aborted_flags[txn_id]

            if not aborted:
                # 4. Commit Phase
                # For OCC, flush buffered writes to WAL & Storage if validation succeeds
                if isinstance(self.protocol, OptimisticConcurrencyControl):
                    buffered = self.protocol.get_buffered_writes(txn_id)
                    commit_ok = self.protocol.on_commit(txn_id)
                    if not commit_ok:
                        aborted = True
                        abort_reason = "OCC validation conflict"
                    else:
                        # Flush buffered writes: Log first, then storage
                        for k, v in buffered.items():
                            old_v = self.storage_engine.get(k)
                            self.log_manager.log_write(txn_id, k, old_v, v)
                            self.storage_engine.put(k, v)
                        self.log_manager.log_commit(txn_id)
                        with self._lock:
                            ctx.status = TxnStatus.COMMITTED
                            ctx.end_time = time.time()
                            ctx.current_op_index = len(ctx.operations)
                        self._emit_event("txn_status", ctx.to_dict())
                        self._emit_event("wal_append", {"op": "COMMIT", "txn_id": txn_id})
                        return
                else:
                    commit_ok = self.protocol.on_commit(txn_id)
                    if not commit_ok:
                        aborted = True
                        abort_reason = "Protocol commit failed"
                    else:
                        self.log_manager.log_commit(txn_id)
                        with self._lock:
                            ctx.status = TxnStatus.COMMITTED
                            ctx.end_time = time.time()
                            ctx.current_op_index = len(ctx.operations)
                        self._emit_event("txn_status", ctx.to_dict())
                        self._emit_event("wal_append", {"op": "COMMIT", "txn_id": txn_id})
                        return

            # If aborted: Rollback uncommitted changes
            if aborted:
                with self._lock:
                    ctx.abort_reason = abort_reason
                    ctx.status = TxnStatus.ABORTED

                # Rollback writes in REVERSE order using recorded old_values
                for key, old_val, _ in reversed(ctx.writes_made):
                    if old_val is None:
                        self.storage_engine.delete(key)
                    else:
                        self.storage_engine.put(key, old_val)

                # Log ABORT in WAL
                self.log_manager.log_abort(txn_id)
                self.protocol.on_abort(txn_id)
                self._emit_event("wal_append", {"op": "ABORT", "txn_id": txn_id, "reason": abort_reason})

                # Check if retryable
                if ctx.retry_count < ctx.max_retries:
                    ctx.retry_count += 1
                    ctx.status = TxnStatus.RETRYING
                    self._emit_event("txn_status", ctx.to_dict())
                    # Exponential backoff jitter
                    time.sleep(0.05 * (2 ** ctx.retry_count))
                    continue
                else:
                    ctx.status = TxnStatus.ABORTED
                    ctx.end_time = time.time()
                    self._emit_event("txn_status", ctx.to_dict())
                    return

    def get_transaction(self, txn_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            ctx = self._txns.get(txn_id)
            return ctx.to_dict() if ctx else None

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [ctx.to_dict() for ctx in self._txns.values()]

    def reset_state(self) -> None:
        """Clean all active state (used for testing or resetting simulator)."""
        with self._lock:
            self.lock_manager.clear()
            self._txns.clear()
            self._aborted_flags.clear()
            self._next_txn_num = 1
            self._logical_ts = 1.0

    def shutdown(self) -> None:
        self.deadlock_detector.stop()
