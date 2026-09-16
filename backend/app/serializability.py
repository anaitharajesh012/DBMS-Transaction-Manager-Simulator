"""
serializability.py - Precedence Graph Builder and Conflict-Serializability Checker.

Reuses find_cycles() from deadlock_detector.py to determine conflict-serializability.
If acyclic, calculates an equivalent serial schedule using Kahn's Topological Sort algorithm.

Parses arbitrary schedules in formats like:
- r1[x] w2[x] r1[y] w1[x] c1 c2
- r1(A), w2(A), r1(B), w1(B), c1, c2
- R1(A) W2(A) C2 C1
"""

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from app.deadlock_detector import find_cycles


@dataclass
class ScheduleOp:
    txn_id: str
    op_type: str  # 'R', 'W', 'C', 'A'
    key: Optional[str] = None
    raw: str = ""
    order: int = 0


@dataclass
class ConflictEdge:
    from_txn: str
    to_txn: str
    conflict_type: str  # "WR", "RW", "WW"
    key: str
    op1_str: str
    op2_str: str


@dataclass
class SerializabilityResult:
    is_serializable: bool
    schedule_ops: List[Dict[str, Any]]
    precedence_graph: Dict[str, List[str]]
    conflicts: List[Dict[str, Any]]
    cycles: List[List[str]]
    equivalent_serial_order: Optional[List[str]] = None
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_schedule(schedule_str: str) -> List[ScheduleOp]:
    """
    Parse schedule string into list of ScheduleOp.
    Supports formats:
      r1[x], w2[x], c1, a2
      r1(A) w2(A) c1 c2
      R1(x) W2(x)
    """
    tokens = re.findall(r"([rwcaRWCA])(\d+)(?:\[([a-zA-Z0-9_]+)\]|\(([a-zA-Z0-9_]+)\))?", schedule_str)
    parsed: List[ScheduleOp] = []

    for idx, (op_char, txn_num, key_bracket, key_paren) in enumerate(tokens):
        op_type = op_char.upper()
        txn_id = f"T{txn_num}"
        key = key_bracket or key_paren or None
        raw = f"{op_type.lower()}{txn_num}" + (f"[{key}]" if key else "")

        parsed.append(ScheduleOp(
            txn_id=txn_id,
            op_type=op_type,
            key=key,
            raw=raw,
            order=idx,
        ))

    return parsed


def check_serializability(schedule_str: str) -> SerializabilityResult:
    """
    Build Precedence Graph, detect cycles, and compute topological sort if acyclic.
    """
    ops = parse_schedule(schedule_str)
    if not ops:
        return SerializabilityResult(
            is_serializable=True,
            schedule_ops=[],
            precedence_graph={},
            conflicts=[],
            cycles=[],
            equivalent_serial_order=[],
            explanation="Empty schedule parsed.",
        )

    # Collect all unique transactions
    all_txns = sorted(list({op.txn_id for op in ops}))
    graph: Dict[str, List[str]] = {t: [] for t in all_txns}
    conflicts: List[ConflictEdge] = []
    edges_set: Set[Tuple[str, str]] = set()

    # Find conflicting pairs (op_i before op_j on same key where at least one is Write)
    for i in range(len(ops)):
        op_i = ops[i]
        if op_i.op_type not in ("R", "W") or not op_i.key:
            continue

        for j in range(i + 1, len(ops)):
            op_j = ops[j]
            if op_j.op_type not in ("R", "W") or not op_j.key:
                continue

            # Check if different transactions on same key
            if op_i.txn_id != op_j.txn_id and op_i.key == op_j.key:
                # At least one must be a WRITE
                if op_i.op_type == "W" or op_j.op_type == "W":
                    ctype = f"{op_i.op_type}{op_j.op_type}"
                    edge = ConflictEdge(
                        from_txn=op_i.txn_id,
                        to_txn=op_j.txn_id,
                        conflict_type=ctype,
                        key=op_i.key,
                        op1_str=op_i.raw,
                        op2_str=op_j.raw,
                    )
                    conflicts.append(edge)

                    if (op_i.txn_id, op_j.txn_id) not in edges_set:
                        edges_set.add((op_i.txn_id, op_j.txn_id))
                        graph[op_i.txn_id].append(op_j.txn_id)

    # Sort neighbor lists for determinism
    for t in graph:
        graph[t].sort()

    # Reuse DFS cycle detection from deadlock_detector
    cycles = find_cycles(graph)

    if cycles:
        cycle_str = " -> ".join(cycles[0])
        return SerializabilityResult(
            is_serializable=False,
            schedule_ops=[asdict(o) for o in ops],
            precedence_graph=graph,
            conflicts=[asdict(c) for c in conflicts],
            cycles=cycles,
            equivalent_serial_order=None,
            explanation=f"Cycle detected in precedence graph: {cycle_str}. Schedule is NOT conflict-serializable.",
        )

    # Acyclic -> Compute Topological Sort (Kahn's Algorithm)
    in_degree = {t: 0 for t in all_txns}
    for u in graph:
        for v in graph[u]:
            in_degree[v] += 1

    queue = [t for t in all_txns if in_degree[t] == 0]
    serial_order: List[str] = []

    while queue:
        queue.sort()  # deterministic tie-breaking
        u = queue.pop(0)
        serial_order.append(u)
        for v in graph[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    order_str = " -> ".join(serial_order)
    return SerializabilityResult(
        is_serializable=True,
        schedule_ops=[asdict(o) for o in ops],
        precedence_graph=graph,
        conflicts=[asdict(c) for c in conflicts],
        cycles=[],
        equivalent_serial_order=serial_order,
        explanation=f"Precedence graph is acyclic. Schedule is conflict-serializable with equivalent serial order: {order_str}.",
    )
