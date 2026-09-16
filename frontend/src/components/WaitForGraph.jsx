import React, { useMemo, useState } from 'react';
import { 
  GitCommit, 
  ShieldAlert, 
  Lock, 
  Unlock, 
  Info,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowRight
} from 'lucide-react';

export default function WaitForGraph({ state }) {
  const [selectedNode, setSelectedNode] = useState(null);

  const waitForGraph = state.wait_for_graph || {};
  const locks = state.locks || [];
  const deadlockHistory = state.deadlock_history || [];
  const latestDeadlock = deadlockHistory.length > 0 ? deadlockHistory[deadlockHistory.length - 1] : null;

  // Extract unique nodes and directed edges
  const { nodes, edges, cycleNodes, cycleEdges } = useMemo(() => {
    const nodeSet = new Set();
    const edgeList = [];

    Object.entries(waitForGraph).forEach(([waiter, blockers]) => {
      nodeSet.add(waiter);
      (blockers || []).forEach((blocker) => {
        nodeSet.add(blocker);
        edgeList.push({ from: waiter, to: blocker });
      });
    });

    // Also include transactions that currently hold locks
    locks.forEach((l) => {
      l.holders.forEach((h) => nodeSet.add(h.txn_id));
      l.waiters.forEach((w) => nodeSet.add(w.txn_id));
    });

    const cycleNodesSet = new Set();
    const cycleEdgesSet = new Set();

    if (latestDeadlock && latestDeadlock.cycle) {
      const cyc = latestDeadlock.cycle;
      cyc.forEach((n) => cycleNodesSet.add(n));
      for (let i = 0; i < cyc.length - 1; i++) {
        cycleEdgesSet.add(`${cyc[i]}->${cyc[i + 1]}`);
      }
    }

    const nodeList = Array.from(nodeSet).map((id, index, arr) => {
      const total = arr.length || 1;
      const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
      const radius = total > 4 ? 140 : 100;
      const x = 280 + radius * Math.cos(angle);
      const y = 175 + radius * Math.sin(angle);
      return { id, x, y };
    });

    return {
      nodes: nodeList,
      edges: edgeList,
      cycleNodes: cycleNodesSet,
      cycleEdges: cycleEdgesSet,
    };
  }, [waitForGraph, locks, latestDeadlock]);

  const nodePosMap = useMemo(() => {
    const m = {};
    nodes.forEach((n) => {
      m[n.id] = { x: n.x, y: n.y };
    });
    return m;
  }, [nodes]);

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-[#0b101b] border border-slate-800/80 rounded p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="font-mono text-[10px] text-blue-400 tracking-wider uppercase block mb-0.5">
            Resource Dependency Visualizer
          </span>
          <h2 className="text-sm font-semibold text-white tracking-tight">
            Lock Contention &amp; Wait-For Dependency Graph
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Directed edge <span className="font-mono text-amber-400">T_i &rarr; T_j</span> denotes transaction <span className="font-mono text-slate-300">T_i</span> blocked waiting for locks held by <span className="font-mono text-slate-300">T_j</span>.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="px-2.5 py-1 bg-[#111726] rounded border border-slate-800 text-slate-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-500"></span> Active Node
          </span>
          <span className="px-2.5 py-1 bg-[#1c0d10] rounded border border-rose-800/80 text-rose-300 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500"></span> Cyclic Deadlock
          </span>
        </div>
      </div>

      {/* Deadlock Incident Report Callout (Structured, not neon) */}
      {latestDeadlock && (
        <div className="bg-[#160b0e] border border-rose-800/70 rounded p-4 text-xs font-mono text-slate-200">
          <div className="flex items-center justify-between pb-2.5 border-b border-rose-900/60">
            <div className="flex items-center gap-2 text-rose-400 font-bold tracking-wider uppercase text-[11px]">
              <ShieldAlert className="w-4 h-4 text-rose-400" />
              <span>Deadlock Detected &bull; Cycle Resolved via Abort</span>
            </div>
            <span className="text-[10px] text-slate-400">
              {new Date(latestDeadlock.timestamp * 1000).toLocaleTimeString()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-3">
            <div>
              <span className="text-[10px] text-slate-400 block uppercase">Cycle Path:</span>
              <span className="text-rose-300 font-bold text-xs">{latestDeadlock.cycle.join(' → ')}</span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block uppercase">Selected Victim:</span>
              <span className="text-white font-bold text-xs bg-rose-950 px-1.5 py-0.5 rounded border border-rose-800">
                {latestDeadlock.victim}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block uppercase">Selection Policy:</span>
              <span className="text-blue-300 font-bold text-xs uppercase">{latestDeadlock.policy}</span>
            </div>
            <div>
              <span className="text-[10px] text-slate-400 block uppercase">Resolution:</span>
              <span className="text-slate-300 text-[11px] font-sans">
                Victim aborted, locks released, automatic retry queued.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Main Canvas & Details Column */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* SVG Graph Canvas (7 cols) */}
        <div className="lg:col-span-7 bg-[#0b101b] border border-slate-800/80 rounded p-5 flex flex-col items-center justify-center min-h-[420px] relative">
          <svg className="w-full h-[350px]" viewBox="0 0 560 350">
            <defs>
              <marker
                id="arrow-std"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="5"
                markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
              </marker>

              <marker
                id="arrow-cycle-highlight"
                viewBox="0 0 10 10"
                refX="22"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
              </marker>
            </defs>

            {/* Subtle grid background */}
            <pattern id="tech-grid" width="24" height="24" patternUnits="userSpaceOnUse">
              <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#131b2e" strokeWidth="0.75" />
            </pattern>
            <rect width="100%" height="100%" fill="url(#tech-grid)" />

            {/* Directed dependency edges */}
            {edges.map((e, idx) => {
              const fromPos = nodePosMap[e.from];
              const toPos = nodePosMap[e.to];
              if (!fromPos || !toPos) return null;

              const isCycleEdge = cycleEdges.has(`${e.from}->${e.to}`);

              return (
                <g key={`wf-edge-${idx}`}>
                  <line
                    x1={fromPos.x}
                    y1={fromPos.y}
                    x2={toPos.x}
                    y2={toPos.y}
                    stroke={isCycleEdge ? '#ef4444' : '#475569'}
                    strokeWidth={isCycleEdge ? '2.5' : '1.5'}
                    strokeDasharray={isCycleEdge ? '4 3' : 'none'}
                    markerEnd={isCycleEdge ? 'url(#arrow-cycle-highlight)' : 'url(#arrow-std)'}
                  />
                </g>
              );
            })}

            {/* Transaction Nodes */}
            {nodes.map((node) => {
              const isCycle = cycleNodes.has(node.id);
              const isVictim = latestDeadlock && latestDeadlock.victim === node.id;
              const isSelected = selectedNode === node.id;

              return (
                <g
                  key={node.id}
                  className="cursor-pointer transition-all"
                  onClick={() => setSelectedNode(node.id)}
                >
                  <circle
                    cx={node.x}
                    cy={node.y}
                    r="20"
                    fill={
                      isVictim ? '#3f0c15' :
                      isCycle ? '#290d14' :
                      isSelected ? '#1e293b' : '#0e1726'
                    }
                    stroke={
                      isVictim ? '#f87171' :
                      isCycle ? '#ef4444' :
                      isSelected ? '#60a5fa' : '#334155'
                    }
                    strokeWidth={isSelected || isCycle ? '2.5' : '1.5'}
                  />

                  <text
                    x={node.x}
                    y={node.y + 4}
                    textAnchor="middle"
                    fill={isCycle ? '#fecaca' : '#f1f5f9'}
                    fontSize="11"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    {node.id.length > 5 ? node.id.slice(0, 5) : node.id}
                  </text>

                  {isVictim && (
                    <text
                      x={node.x}
                      y={node.y - 25}
                      textAnchor="middle"
                      fill="#f87171"
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      VICTIM
                    </text>
                  )}
                </g>
              );
            })}

            {nodes.length === 0 && (
              <text x="280" y="175" textAnchor="middle" fill="#64748b" fontSize="12" fontFamily="monospace">
                No active locks or wait-for dependencies
              </text>
            )}
          </svg>

          <div className="absolute bottom-3 left-4 text-[11px] font-mono text-slate-400">
            Click any node to isolate its lock dependencies
          </div>
        </div>

        {/* Node Inspector & Lock State Table (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Node Inspector */}
          <div className="bg-[#0b101b] border border-slate-800/80 rounded p-4">
            <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block mb-1">
              Node Diagnosis
            </span>
            <h3 className="text-xs font-semibold text-white tracking-tight mb-3 flex items-center gap-1.5">
              <Info className="w-3.5 h-3.5 text-blue-400" />
              <span>Inspection: {selectedNode || 'Select a Node'}</span>
            </h3>

            {selectedNode ? (
              <div className="space-y-2.5 font-mono text-xs">
                <div>
                  <span className="text-[11px] text-slate-400 block mb-1">Blocked Behind:</span>
                  <div className="flex flex-wrap gap-1">
                    {(waitForGraph[selectedNode] || []).length > 0 ? (
                      waitForGraph[selectedNode].map((b) => (
                        <span key={b} className="bg-amber-950/50 text-amber-300 border border-amber-800/60 px-2 py-0.5 rounded text-[11px]">
                          {b}
                        </span>
                      ))
                    ) : (
                      <span className="text-slate-400 text-[11px] italic">Not currently blocked</span>
                    )}
                  </div>
                </div>

                <div>
                  <span className="text-[11px] text-slate-400 block mb-1">Blocking Others (Waiters):</span>
                  <div className="flex flex-wrap gap-1">
                    {Object.entries(waitForGraph)
                      .filter(([_, blockers]) => (blockers || []).includes(selectedNode))
                      .map(([waiter]) => (
                        <span key={waiter} className="bg-blue-950/50 text-blue-300 border border-blue-800/60 px-2 py-0.5 rounded text-[11px]">
                          {waiter}
                        </span>
                      ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400 font-sans">
                Click any circle in the graph to inspect which transactions it is currently waiting on or blocking.
              </p>
            )}
          </div>

          {/* Active Key Locks Table */}
          <div className="bg-[#0b101b] border border-slate-800/80 rounded p-4">
            <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block mb-1">
              Resource Allocator
            </span>
            <h3 className="text-xs font-semibold text-white tracking-tight mb-3 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>Active Key Lock Table</span>
            </h3>

            <div className="max-h-60 overflow-y-auto space-y-2 font-mono text-xs pr-1">
              {locks.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">No locks currently held.</div>
              ) : (
                locks.map((l) => (
                  <div key={l.key} className="p-2.5 rounded bg-[#0e1422] border border-slate-800/80">
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-cyan-300">KEY: {l.key}</span>
                      <span className="text-[10px] text-slate-400">
                        {l.holders.length} holder(s), {l.waiters.length} waiting
                      </span>
                    </div>

                    <div className="space-y-1 text-[11px]">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="text-emerald-400 text-[10px] uppercase">Holders:</span>
                        {l.holders.map((h, i) => (
                          <span key={i} className="bg-emerald-950/50 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-800/50">
                            {h.txn_id} [{h.mode}]
                          </span>
                        ))}
                      </div>

                      {l.waiters.length > 0 && (
                        <div className="flex items-center gap-1.5 flex-wrap pt-1">
                          <span className="text-amber-400 text-[10px] uppercase">Waiters:</span>
                          {l.waiters.map((w, i) => (
                            <span key={i} className="bg-amber-950/50 text-amber-300 px-1.5 py-0.5 rounded border border-amber-800/50">
                              {w.txn_id} [{w.mode}]
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
