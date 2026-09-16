"""
deadlock_detector.py - Deadlock Detection via DFS Cycle Search & Victim Selection.

Responsibilities:
1. Cycle Detection: Depth-First Search (DFS) with 3-color graph coloring
   (WHITE=unvisited, GRAY=active on stack, BLACK=finished) to find all simple cycles.
   This algorithm is exported as find_cycles() and REUSED by the Serializability Precedence Graph.
2. Background Polling Thread: Periodically polls LockManager's wait-for graph.
3. Swappable Victim Selection:
   - "youngest": Transaction with the latest start timestamp (highest timestamp).
   - "fewest_locks": Transaction currently holding the fewest locks.
4. Victim Abort Signaling: Marks the victim transaction for abort, unblocking waiters
   and restoring system progress.
5. Telemetry: Logs deadlock events (cycle path, victim, policy) for real-time visualization.
"""

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def find_cycles(graph: Dict[str, List[str]]) -> List[List[str]]:
    """
    Find all elementary cycles in a directed graph using DFS.
    Reused across Deadlock Detection and Serializability Precedence Graph!
    graph: {node: [neighbors (outgoing edges)]}
    Returns a list of cycles, each cycle being a list of node IDs forming a cycle: [n1, n2, ..., n1]
    """
    WHITE = 0  # unvisited
    GRAY = 1   # currently on recursion stack
    BLACK = 2  # fully visited

    colors: Dict[str, int] = {node: WHITE for node in graph}
    # Ensure all target nodes exist in graph keys
    for neighbors in graph.values():
        for n in neighbors:
            if n not in colors:
                colors[n] = WHITE

    cycles: List[List[str]] = []
    parent: Dict[str, Optional[str]] = {node: None for node in colors}
    visited_cycles: Set[Tuple[str, ...]] = set()

    def dfs(u: str, stack: List[str]):
        colors[u] = GRAY
        stack.append(u)

        for v in graph.get(u, []):
            if colors.get(v) == GRAY:
                # Cycle found! Extract cycle from stack
                if v in stack:
                    idx = stack.index(v)
                    cycle_nodes = stack[idx:] + [v]
                    # Normalize cycle representation for deduplication
                    canonical = tuple(cycle_nodes[:-1])
                    # Rotate canonical so min element is first
                    if canonical:
                        min_idx = canonical.index(min(canonical))
                        rotated = canonical[min_idx:] + canonical[:min_idx]
                        if rotated not in visited_cycles:
                            visited_cycles.add(rotated)
                            cycles.append(cycle_nodes)
            elif colors.get(v) == WHITE:
                parent[v] = u
                dfs(v, stack)

        stack.pop()
        colors[u] = BLACK

    for node in sorted(list(colors.keys())):
        if colors[node] == WHITE:
            dfs(node, [])

    return cycles


class DeadlockEvent:
    def __init__(
        self,
        cycle: List[str],
        victim: str,
        policy: str,
        timestamp: float,
    ):
        self.cycle = cycle
        self.victim = victim
        self.policy = policy
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle": self.cycle,
            "victim": self.victim,
            "policy": self.policy,
            "timestamp": self.timestamp,
        }


class DeadlockDetector:
    """
    Background deadlock detector polling LockManager's wait-for graph.
    """

    def __init__(
        self,
        get_wait_for_graph_fn: Callable[[], Dict[str, List[str]]],
        get_locks_held_fn: Callable[[str], Dict[str, str]],
        get_txn_timestamp_fn: Callable[[str], float],
        abort_victim_fn: Callable[[str, str], None],
        policy: str = "youngest",  # "youngest" or "fewest_locks"
        poll_interval: float = 0.1,  # 100ms
    ):
        self.get_wait_for_graph = get_wait_for_graph_fn
        self.get_locks_held = get_locks_held_fn
        self.get_txn_timestamp = get_txn_timestamp_fn
        self.abort_victim = abort_victim_fn
        self.policy = policy.lower()
        self.poll_interval = poll_interval

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._deadlock_history: List[DeadlockEvent] = []
        self._on_deadlock_detected_cb: Optional[Callable[[DeadlockEvent], None]] = None

    def set_policy(self, policy: str) -> None:
        with self._lock:
            self.policy = policy.lower()

    def set_callback(self, cb: Callable[[DeadlockEvent], None]) -> None:
        with self._lock:
            self._on_deadlock_detected_cb = cb

    def start(self) -> None:
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(
                    target=self._run_loop, name="DeadlockDetectorThread", daemon=True
                )
                self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        while self._running:
            try:
                self.check_and_resolve()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def check_and_resolve(self) -> Optional[DeadlockEvent]:
        """Check wait-for graph for cycles and resolve first detected cycle."""
        wf = self.get_wait_for_graph()
        if not wf:
            return None

        cycles = find_cycles(wf)
        if not cycles:
            return None

        # Resolve the first cycle
        cycle = cycles[0]
        cycle_txns = list(dict.fromkeys(cycle[:-1]))  # unique cycle participants

        victim = self._select_victim(cycle_txns)
        event = DeadlockEvent(
            cycle=cycle,
            victim=victim,
            policy=self.policy,
            timestamp=time.time(),
        )

        with self._lock:
            self._deadlock_history.append(event)
            if len(self._deadlock_history) > 100:
                self._deadlock_history = self._deadlock_history[-50:]

        # Trigger abort callback
        self.abort_victim(victim, f"Deadlock cycle detected: {' -> '.join(cycle)}. Aborted via {self.policy} policy.")

        if self._on_deadlock_detected_cb:
            try:
                self._on_deadlock_detected_cb(event)
            except Exception:
                pass

        return event

    def _select_victim(self, cycle_txns: List[str]) -> str:
        """Apply active victim selection policy."""
        if not cycle_txns:
            return ""

        if self.policy == "fewest_locks":
            # Select txn holding fewest locks (break tie with youngest)
            counts = {
                t: (len(self.get_locks_held(t)), -self.get_txn_timestamp(t))
                for t in cycle_txns
            }
            return min(counts.keys(), key=lambda t: counts[t])

        # Default: "youngest" (highest start timestamp)
        return max(cycle_txns, key=lambda t: self.get_txn_timestamp(t))

    def get_history(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._deadlock_history]
