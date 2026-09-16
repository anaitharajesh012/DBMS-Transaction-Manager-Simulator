"""
recovery_manager.py - ARIES-Lite 3-Pass Crash Recovery Manager.

Implements genuine ARIES-style recovery:
1. Analysis Pass:
   - Scans the WAL forward from start / checkpoint.
   - Identifies Winner transactions (committed before crash) and Loser transactions
     (active / uncommitted at crash point).
   - Tracks the last LSN for each active loser transaction.
2. Redo Pass (Repeating History):
   - Scans forward through the log.
   - Replays ALL logged WRITE records (even from uncommitted loser transactions)
     to re-establish the exact storage state at the instant of the crash.
3. Undo Pass:
   - Scans backward through the WAL undoing operations of uncommitted loser transactions
     in reverse chronological order using old_value.
   - Writes Compensation Log Records (CLRs) to the WAL to ensure idempotent recovery.
   - Writes final ABORT records for each loser transaction upon full undo.

Returns detailed step-by-step diagnostic trace for the visual frontend replay.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set

from app.log_manager import LogManager, LogRecord
from app.storage_engine import StorageEngine


@dataclass
class RecoveryAction:
    phase: str  # "ANALYSIS", "REDO", "UNDO"
    lsn: int
    txn_id: str
    op_type: str
    key: Optional[str]
    old_value: Optional[Any]
    new_value: Optional[Any]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryReport:
    winners: List[str]
    losers: List[str]
    already_aborted: List[str]
    analysis_steps: List[Dict[str, Any]]
    redo_steps: List[Dict[str, Any]]
    undo_steps: List[Dict[str, Any]]
    clrs_written: List[Dict[str, Any]]
    final_storage: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RecoveryManager:
    """
    Executes ARIES-lite 3-pass crash recovery over an on-disk WAL.
    """

    def __init__(self, log_manager: LogManager, storage_engine: StorageEngine):
        self.log_manager = log_manager
        self.storage_engine = storage_engine

    def recover(self) -> RecoveryReport:
        """
        Execute full 3-pass recovery:
        1. Analysis Pass
        2. Redo Pass
        3. Undo Pass
        """
        all_records = self.log_manager.read_all()

        # ----------------------------------------------------
        # Phase 1: Analysis Pass
        # ----------------------------------------------------
        active_txns: Set[str] = set()
        committed_txns: Set[str] = set()
        aborted_txns: Set[str] = set()
        analysis_steps: List[Dict[str, Any]] = []

        for r in all_records:
            if r.op_type == "BEGIN":
                active_txns.add(r.txn_id)
                analysis_steps.append({
                    "lsn": r.lsn,
                    "txn_id": r.txn_id,
                    "event": f"Transaction {r.txn_id} started -> marked ACTIVE",
                })
            elif r.op_type == "COMMIT":
                active_txns.discard(r.txn_id)
                committed_txns.add(r.txn_id)
                analysis_steps.append({
                    "lsn": r.lsn,
                    "txn_id": r.txn_id,
                    "event": f"Transaction {r.txn_id} committed -> marked WINNER",
                })
            elif r.op_type == "ABORT":
                active_txns.discard(r.txn_id)
                aborted_txns.add(r.txn_id)
                analysis_steps.append({
                    "lsn": r.lsn,
                    "txn_id": r.txn_id,
                    "event": f"Transaction {r.txn_id} aborted before crash -> marked ABORTED",
                })

        loser_txns = sorted(list(active_txns))
        winner_txns = sorted(list(committed_txns))
        already_aborted = sorted(list(aborted_txns))

        # Clear storage engine to simulate fresh restart from raw storage
        self.storage_engine.clear()

        # ----------------------------------------------------
        # Phase 2: Redo Pass (Repeating History)
        # ----------------------------------------------------
        redo_steps: List[Dict[str, Any]] = []

        for r in all_records:
            if r.op_type in ("WRITE", "CLR"):
                # Apply write to storage engine
                self.storage_engine.put(r.key, r.new_value)
                redo_steps.append({
                    "lsn": r.lsn,
                    "txn_id": r.txn_id,
                    "op_type": r.op_type,
                    "key": r.key,
                    "value_applied": r.new_value,
                    "status": "REDO applied to restore pre-crash state",
                })

        # ----------------------------------------------------
        # Phase 3: Undo Pass (Rollback Losers)
        # ----------------------------------------------------
        undo_steps: List[Dict[str, Any]] = []
        clrs_written: List[Dict[str, Any]] = []

        # Scan backwards through all records to undo loser writes
        for r in reversed(all_records):
            if r.txn_id in active_txns and r.op_type == "WRITE":
                # Rollback this write using old_value
                if r.old_value is None:
                    self.storage_engine.delete(r.key)
                else:
                    self.storage_engine.put(r.key, r.old_value)

                # Write Compensation Log Record (CLR) to WAL
                clr = self.log_manager.log_clr(
                    txn_id=r.txn_id,
                    key=r.key,
                    undid_to_value=r.old_value,
                    undo_next_lsn=r.prev_lsn,
                )

                undo_info = {
                    "undone_lsn": r.lsn,
                    "clr_lsn": clr.lsn,
                    "txn_id": r.txn_id,
                    "key": r.key,
                    "restored_value": r.old_value,
                    "action": f"Undid write on key '{r.key}' -> restored to {r.old_value}",
                }
                undo_steps.append(undo_info)
                clrs_written.append(clr.to_dict())

        # Write ABORT records for all loser transactions
        for loser_id in loser_txns:
            self.log_manager.log_abort(loser_id)

        report = RecoveryReport(
            winners=winner_txns,
            losers=loser_txns,
            already_aborted=already_aborted,
            analysis_steps=analysis_steps,
            redo_steps=redo_steps,
            undo_steps=undo_steps,
            clrs_written=clrs_written,
            final_storage=self.storage_engine.snapshot(),
        )

        return report
