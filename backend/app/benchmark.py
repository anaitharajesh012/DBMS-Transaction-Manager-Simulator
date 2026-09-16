"""
benchmark.py - Multi-Threaded Synthetic Workload Benchmark Runner.

Compares:
1. Concurrency Protocols: Strict 2PL vs Timestamp Ordering vs OCC vs MVCC
2. Deadlock Resolution: Detection (Youngest / Fewest Locks) vs Prevention (Wound-Wait / Wait-Die)

Parameters:
- num_transactions: Total transactions per protocol (e.g. 50-200)
- concurrency: Number of worker threads running concurrently (e.g. 4-10)
- contention: "high" (2 hot keys) vs "medium" (5 keys) vs "low" (20 keys)
- write_ratio: Fraction of operations that are writes (0.2 to 0.8)
"""

import os
import random
import tempfile
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from app.log_manager import LogManager
from app.storage_engine import StorageEngine
from app.transaction_manager import TransactionManager, TxnOp, TxnStatus


@dataclass
class ProtocolBenchmarkResult:
    protocol: str
    mode: str
    total_txns: int
    committed: int
    aborted: int
    throughput_tps: float
    avg_latency_ms: float
    abort_rate_pct: float
    duration_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_single_workload(
    protocol: str,
    deadlock_mode: str = "detection",
    prevention_scheme: str = "wound_wait",
    victim_policy: str = "youngest",
    num_txns: int = 50,
    concurrency: int = 5,
    contention: str = "high",
    write_ratio: float = 0.5,
) -> ProtocolBenchmarkResult:
    # Key space based on contention
    if contention == "high":
        keys = ["HOT_A", "HOT_B"]
    elif contention == "medium":
        keys = ["K1", "K2", "K3", "K4", "K5"]
    else:
        keys = [f"KEY_{i}" for i in range(20)]

    initial_data = {k: 1000 for k in keys}
    storage = StorageEngine(initial_data)

    fd, wal_path = tempfile.mkstemp(suffix=".bench.wal")
    os.close(fd)
    log = LogManager(wal_path)

    tm = TransactionManager(
        storage_engine=storage,
        log_manager=log,
        protocol_type=protocol,
        deadlock_mode=deadlock_mode,
        prevention_scheme=prevention_scheme,
        victim_policy=victim_policy,
    )

    # Generate synthetic transactions
    txns_ops: List[List[TxnOp]] = []
    for i in range(num_txns):
        ops_count = random.randint(2, 4)
        ops = []
        for _ in range(ops_count):
            k = random.choice(keys)
            is_write = random.random() < write_ratio
            if is_write:
                ops.append(TxnOp(op_type="WRITE", key=k, value=random.randint(10, 500)))
            else:
                ops.append(TxnOp(op_type="READ", key=k))
        txns_ops.append(ops)

    start_time = time.time()
    submitted_ids = []

    # Submit all transactions (with bounded retries = 2)
    for i, ops in enumerate(txns_ops):
        tid = tm.submit_transaction(ops, txn_id=f"B_{protocol}_{i}", max_retries=2)
        submitted_ids.append(tid)

    # Wait for completion (with timeout)
    max_wait = 15.0
    while time.time() - start_time < max_wait:
        all_done = True
        for tid in submitted_ids:
            tx = tm.get_transaction(tid)
            if tx and tx["status"] not in ("COMMITTED", "ABORTED"):
                all_done = False
                break
        if all_done:
            break
        time.sleep(0.02)

    total_duration = max(time.time() - start_time, 0.001)

    committed = 0
    aborted = 0
    latencies = []

    for tid in submitted_ids:
        tx = tm.get_transaction(tid)
        if tx:
            if tx["status"] == "COMMITTED":
                committed += 1
            else:
                aborted += 1
            if tx["end_time"] and tx["start_time"]:
                latencies.append((tx["end_time"] - tx["start_time"]) * 1000.0)

    tm.shutdown()
    if os.path.exists(wal_path):
        try:
            os.remove(wal_path)
        except Exception:
            pass

    throughput = round(committed / total_duration, 2)
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
    abort_rate = round((aborted / num_txns) * 100, 2) if num_txns > 0 else 0.0

    return ProtocolBenchmarkResult(
        protocol=protocol,
        mode=f"{deadlock_mode}:{prevention_scheme if deadlock_mode == 'prevention' else victim_policy}",
        total_txns=num_txns,
        committed=committed,
        aborted=aborted,
        throughput_tps=throughput,
        avg_latency_ms=avg_latency,
        abort_rate_pct=abort_rate,
        duration_sec=round(total_duration, 3),
    )


def run_full_suite(
    num_txns: int = 40,
    contention: str = "high",
    write_ratio: float = 0.5,
) -> Dict[str, Any]:
    """Run full benchmark comparing 4 protocols and deadlock prevention schemes."""
    protocols = ["2PL", "TO", "OCC", "MVCC"]
    protocol_results = []

    for p in protocols:
        res = run_single_workload(
            protocol=p,
            deadlock_mode="detection",
            victim_policy="youngest",
            num_txns=num_txns,
            contention=contention,
            write_ratio=write_ratio,
        )
        protocol_results.append(res.to_dict())

    # Comparison: Detection vs Prevention on 2PL
    deadlock_results = []
    deadlock_configs = [
        ("detection", "youngest", "youngest"),
        ("detection", "fewest_locks", "fewest_locks"),
        ("prevention", "wound_wait", "wound_wait"),
        ("prevention", "wait_die", "wait_die"),
    ]

    for mode, scheme, label in deadlock_configs:
        res = run_single_workload(
            protocol="2PL",
            deadlock_mode=mode,
            prevention_scheme=scheme,
            victim_policy=scheme,
            num_txns=num_txns,
            contention="high",
            write_ratio=0.7,
        )
        data = res.to_dict()
        data["strategy_label"] = f"{mode.capitalize()} ({label})"
        deadlock_results.append(data)

    return {
        "protocols": protocol_results,
        "deadlock_comparison": deadlock_results,
        "parameters": {
            "num_txns": num_txns,
            "contention": contention,
            "write_ratio": write_ratio,
        },
    }
