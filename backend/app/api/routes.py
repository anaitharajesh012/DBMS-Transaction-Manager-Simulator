"""
routes.py - FastAPI route handlers and WebSocket connection manager.
"""

import asyncio
import os
import threading
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect

from app.api.schemas import (
    BatchTxnRequest,
    BenchmarkRequest,
    ConfigRequest,
    IsolationScenarioRequest,
    ResetRequest,
    SerializabilityRequest,
    SubmitTxnRequest,
)
from app.benchmark import run_full_suite
from app.concurrency.mvcc import MultiVersionConcurrencyControl
from app.log_manager import LogManager
from app.recovery_manager import RecoveryManager
from app.scenarios.isolation_scenarios import (
    run_dirty_read_scenario,
    run_lost_update_scenario,
    run_non_repeatable_read_scenario,
    run_phantom_read_scenario,
)
from app.serializability import check_serializability
from app.storage_engine import StorageEngine
from app.transaction_manager import IsolationLevel, TransactionManager, TxnOp

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        with self._lock:
            self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        with self._lock:
            self.active_connections.discard(websocket)

    def broadcast_sync(self, event_type: str, data: Any):
        """Thread-safe call from transaction background threads into asyncio loop."""
        if not self.loop or not self.loop.is_running():
            return
        payload = {"type": event_type, "data": data}
        asyncio.run_coroutine_threadsafe(self._broadcast(payload), self.loop)

    async def _broadcast(self, payload: Dict[str, Any]):
        dead = []
        with self._lock:
            conns = list(self.active_connections)
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            with self._lock:
                for ws in dead:
                    self.active_connections.discard(ws)


ws_manager = ConnectionManager()

# Global system state
DEFAULT_STORAGE = {"A": 500, "B": 500, "C": 1000, "X": 100, "Y": 200}
wal_file = os.path.abspath("db_simulator.wal")
storage = StorageEngine(DEFAULT_STORAGE)
log_mgr = LogManager(wal_file)


def _telemetry_callback(event_type: str, payload: Dict[str, Any]):
    ws_manager.broadcast_sync(event_type, payload)


tm = TransactionManager(
    storage_engine=storage,
    log_manager=log_mgr,
    protocol_type="2PL",
    deadlock_mode="detection",
    victim_policy="youngest",
    event_callback=_telemetry_callback,
)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial full state snapshot upon connecting
        await websocket.send_json({"type": "full_state", "data": _get_full_state()})
        while True:
            # Keep listening for client pings or commands
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


def _get_full_state() -> Dict[str, Any]:
    wf = tm.lock_manager.get_wait_for_graph()
    locks = tm.lock_manager.get_all_locks()
    txns = tm.get_all_transactions()
    store_snap = storage.snapshot()
    wal_records = [r.to_dict() for r in log_mgr.get_in_memory_records()[-100:]]
    deadlock_hist = tm.deadlock_detector.get_history()

    return {
        "protocol": tm.protocol_type,
        "deadlock_mode": "prevention" if tm.lock_manager.prevention_mode != "none" else "detection",
        "prevention_scheme": tm.lock_manager.prevention_mode,
        "victim_policy": tm.deadlock_detector.policy,
        "storage": store_snap,
        "wait_for_graph": wf,
        "locks": locks,
        "transactions": txns,
        "wal_records": wal_records,
        "deadlock_history": deadlock_hist,
    }


@router.get("/state")
def get_state():
    """Retrieve full system state snapshot."""
    return _get_full_state()


@router.get("/state/locks")
def get_locks():
    return {
        "wait_for_graph": tm.lock_manager.get_wait_for_graph(),
        "locks": tm.lock_manager.get_all_locks(),
    }


@router.get("/state/log")
def get_log():
    return [r.to_dict() for r in log_mgr.read_all()]


@router.get("/state/storage")
def get_storage():
    return storage.snapshot()


@router.post("/transactions")
def submit_transaction(req: SubmitTxnRequest):
    """Submit a single transaction with a list of operations."""
    ops = [
        TxnOp(
            op_type=op.op_type.upper(),
            key=op.key,
            value=op.value,
            duration=op.duration,
        )
        for op in req.operations
    ]

    try:
        iso_level = IsolationLevel[req.isolation_level.upper()]
    except KeyError:
        iso_level = IsolationLevel.SERIALIZABLE

    tid = tm.submit_transaction(
        operations=ops,
        txn_id=req.txn_id,
        isolation_level=iso_level,
        max_retries=req.max_retries,
    )
    return {"txn_id": tid, "status": "SUBMITTED"}


@router.post("/transactions/batch")
def submit_batch(req: BatchTxnRequest):
    """Submit multiple transactions concurrently."""
    submitted = []
    for t_req in req.transactions:
        ops = [
            TxnOp(
                op_type=op.op_type.upper(),
                key=op.key,
                value=op.value,
                duration=op.duration,
            )
            for op in t_req.operations
        ]
        try:
            iso = IsolationLevel[t_req.isolation_level.upper()]
        except KeyError:
            iso = IsolationLevel.SERIALIZABLE

        tid = tm.submit_transaction(
            operations=ops,
            txn_id=t_req.txn_id,
            isolation_level=iso,
            max_retries=t_req.max_retries,
        )
        submitted.append(tid)
    return {"submitted": submitted, "count": len(submitted)}


@router.post("/config")
def update_config(req: ConfigRequest):
    """Update active concurrency protocol or deadlock mode."""
    if req.protocol:
        try:
            tm.set_protocol(req.protocol)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if req.deadlock_mode or req.victim_policy or req.prevention_scheme:
        mode = req.deadlock_mode or ("prevention" if tm.lock_manager.prevention_mode != "none" else "detection")
        scheme = req.prevention_scheme or tm.lock_manager.prevention_mode or "wound_wait"
        policy = req.victim_policy or tm.deadlock_detector.policy or "youngest"
        tm.set_deadlock_mode(mode=mode, prevention_scheme=scheme, victim_policy=policy)

    state = _get_full_state()
    ws_manager.broadcast_sync("full_state", state)
    return {"status": "CONFIG_UPDATED", "config": state}


@router.post("/reset")
def reset_system(req: Optional[ResetRequest] = None):
    """Reset the database engine, WAL, and transaction manager state."""
    tm.reset_state()
    storage.clear()
    seed = req.initial_storage if req and req.initial_storage else DEFAULT_STORAGE
    for k, v in seed.items():
        storage.put(k, v)
    log_mgr.clear()

    # Re-seed MVCC if active
    if isinstance(tm.protocol, MultiVersionConcurrencyControl):
        for k, v in storage.snapshot().items():
            tm.protocol.initialize_key(k, v, timestamp=0.0)

    state = _get_full_state()
    ws_manager.broadcast_sync("full_state", state)
    return {"status": "RESET_COMPLETE", "storage": storage.snapshot()}


@router.post("/crash")
def simulate_crash():
    """Simulate a sudden crash: kill volatile memory, preserve disk WAL."""
    pre_crash_storage = storage.snapshot()
    active_in_flight = [
        t["txn_id"] for t in tm.get_all_transactions()
        if t["status"] in ("NEW", "RUNNING", "WAITING")
    ]

    # Stop detector and clear volatile memory
    tm.shutdown()
    tm.reset_state()
    storage.clear()

    crash_info = {
        "status": "CRASHED",
        "pre_crash_storage": pre_crash_storage,
        "active_in_flight_txns": active_in_flight,
        "volatile_storage_erased": True,
        "wal_preserved_on_disk": True,
    }
    ws_manager.broadcast_sync("system_crashed", crash_info)
    return crash_info


@router.post("/recover")
def run_recovery():
    """Trigger ARIES-lite 3-pass crash recovery."""
    rm = RecoveryManager(log_mgr, storage)
    report = rm.recover()

    # Restart TransactionManager with clean state on top of recovered storage
    tm.reset_state()
    if isinstance(tm.protocol, MultiVersionConcurrencyControl):
        for k, v in storage.snapshot().items():
            tm.protocol.initialize_key(k, v, timestamp=0.0)

    report_dict = report.to_dict()
    ws_manager.broadcast_sync("recovery_completed", report_dict)
    ws_manager.broadcast_sync("full_state", _get_full_state())
    return report_dict


@router.post("/serializability/check")
def api_check_serializability(req: SerializabilityRequest):
    """Parse schedule and check conflict-serializability with precedence graph."""
    res = check_serializability(req.schedule)
    return res.to_dict()


@router.post("/isolation/run")
def api_run_isolation_scenario(req: IsolationScenarioRequest):
    """Execute pre-built anomaly scenarios."""
    sc = req.scenario.lower()
    level = req.isolation_level.upper()

    if sc == "dirty_read":
        return run_dirty_read_scenario(level)
    elif sc == "non_repeatable_read":
        return run_non_repeatable_read_scenario(level)
    elif sc == "lost_update":
        return run_lost_update_scenario(level)
    elif sc == "phantom_read":
        return run_phantom_read_scenario(level)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {req.scenario}. Choose dirty_read, non_repeatable_read, lost_update, or phantom_read.",
        )


@router.get("/mvcc/versions")
def get_mvcc_versions(key: Optional[str] = None):
    """Retrieve version chains for MVCC inspection."""
    if not isinstance(tm.protocol, MultiVersionConcurrencyControl):
        raise HTTPException(
            status_code=400,
            detail="MVCC protocol is not currently active. Switch to MVCC first.",
        )
    if key:
        return {"key": key, "versions": tm.protocol.get_version_chain(key)}
    return {"version_chains": tm.protocol.get_all_version_chains()}


@router.get("/mvcc/time-travel")
def time_travel_query(key: str = Query(...), timestamp: float = Query(...)):
    """Execute historical time-travel query as of a past timestamp."""
    if not isinstance(tm.protocol, MultiVersionConcurrencyControl):
        raise HTTPException(
            status_code=400,
            detail="MVCC protocol is not currently active.",
        )
    val = tm.protocol.get_version_at(key, timestamp)
    return {
        "key": key,
        "as_of_timestamp": timestamp,
        "value": val,
        "chain": tm.protocol.get_version_chain(key),
    }


@router.post("/benchmark")
def api_benchmark(req: BenchmarkRequest):
    """Execute multi-threaded benchmark suite across protocols and deadlock modes."""
    results = run_full_suite(
        num_txns=req.num_txns,
        contention=req.contention,
        write_ratio=req.write_ratio,
    )
    return results
