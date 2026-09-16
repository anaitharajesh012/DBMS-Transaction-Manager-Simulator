import React, { useState } from 'react';
import { 
  Network, 
  CheckCircle2, 
  XCircle, 
  Play, 
  ArrowRight, 
  BookOpen, 
  Repeat, 
  AlertCircle 
} from 'lucide-react';

export default function SerializabilityChecker({ onNotify }) {
  const [scheduleInput, setScheduleInput] = useState('r1[x] w2[x] r1[y] w1[x] c1 c2');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const presets = [
    {
      label: 'Conflict-Serializable (2-Txn)',
      schedule: 'r1[x] w1[x] r2[x] w2[x] c1 c2',
      expected: 'Serializable (T1 → T2)',
    },
    {
      label: 'Cyclic RW/WW Violation',
      schedule: 'r1[x] w2[x] w1[x] c1 c2',
      expected: 'Non-Serializable (Cycle: T1 → T2 → T1)',
    },
    {
      label: 'Cross-Key Dependency Deadlock',
      schedule: 'r1[x] r2[y] w1[y] w2[x] c1 c2',
      expected: 'Non-Serializable (Cycle: T1 → T2 → T1)',
    },
    {
      label: '3-Txn Cascading Serial Order',
      schedule: 'r1[x] w1[x] r2[x] w2[y] r3[y] w3[z] c1 c2 c3',
      expected: 'Serializable (T1 → T2 → T3)',
    },
  ];

  const handleCheck = async (schedToCheck = scheduleInput) => {
    if (!schedToCheck.trim()) return;
    setLoading(true);
    try {
      const res = await fetch('/api/serializability/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schedule: schedToCheck }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        if (data.is_serializable) {
          onNotify(`Schedule is Conflict-Serializable: ${data.equivalent_serial_order.join(' → ')}`, 'success');
        } else {
          onNotify(`Schedule is NOT Conflict-Serializable (Cycle detected)`, 'error');
        }
      }
    } catch (err) {
      onNotify('Failed to evaluate schedule', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <Network className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-slate-100">Conflict-Serializability & Precedence Graph Checker</h2>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Determines whether an interleaved schedule is conflict-equivalent to a serial execution by building a directed Precedence Graph (Serialization Graph) where edges represent Write-Read (WR), Read-Write (RW), or Write-Write (WW) conflicts. Cycle detection is powered by the same DFS engine as the Deadlock Detector.
        </p>
      </div>

      {/* Input Form & Presets */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
            Schedule Expression (Standard DBMS Notation)
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              value={scheduleInput}
              onChange={(e) => setScheduleInput(e.target.value)}
              placeholder="e.g. r1[x] w2[x] r1[y] w1[x] c1 c2"
              className="flex-1 bg-slate-950 text-sm text-slate-100 font-mono px-4 py-2.5 rounded-lg border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              onClick={() => handleCheck(scheduleInput)}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              Analyze
            </button>
          </div>
          <div className="text-[11px] text-slate-500 mt-1.5 font-mono">
            Supported formats: r1[x] w2[x] c1 c2 or r1(A) w2(A) c1 c2. Operations: r (Read), w (Write), c (Commit), a (Abort).
          </div>
        </div>

        {/* Presets */}
        <div>
          <span className="text-xs text-slate-400 font-bold block mb-2">Textbook Benchmark Schedules:</span>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5">
            {presets.map((p, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setScheduleInput(p.schedule);
                  handleCheck(p.schedule);
                }}
                className="text-left p-2.5 rounded-lg bg-slate-950/60 hover:bg-slate-950 border border-slate-800 hover:border-indigo-500/50 transition group"
              >
                <div className="text-xs font-bold text-slate-200 group-hover:text-indigo-300 truncate">
                  {p.label}
                </div>
                <div className="font-mono text-[11px] text-slate-400 truncate mt-0.5">
                  {p.schedule}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Analysis Result */}
      {result && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-xl space-y-6">
          {/* Status Header */}
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              {result.is_serializable ? (
                <CheckCircle2 className="w-8 h-8 text-emerald-400 flex-shrink-0" />
              ) : (
                <XCircle className="w-8 h-8 text-rose-400 flex-shrink-0" />
              )}
              <div>
                <h3 className="text-base font-bold text-slate-100">
                  {result.is_serializable ? (
                    <span className="text-emerald-400">Conflict-Serializable Schedule</span>
                  ) : (
                    <span className="text-rose-400">Non-Conflict-Serializable (Cycle Detected)</span>
                  )}
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">{result.explanation}</p>
              </div>
            </div>

            {result.is_serializable && result.equivalent_serial_order && (
              <div className="text-right">
                <span className="text-[11px] text-slate-400 block mb-1 uppercase font-mono">Equivalent Serial Order:</span>
                <span className="bg-emerald-950/80 text-emerald-300 font-mono text-sm font-bold px-3 py-1.5 rounded-lg border border-emerald-800/80">
                  {result.equivalent_serial_order.join(' → ')}
                </span>
              </div>
            )}
          </div>

          {/* Graph Visualization & Conflict Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Precedence Graph Visual */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Network className="w-4 h-4 text-indigo-400" />
                Precedence Graph Adjacency
              </h4>

              <div className="space-y-2.5 font-mono text-xs">
                {Object.entries(result.precedence_graph || {}).map(([fromNode, toNodes]) => (
                  <div key={fromNode} className="flex items-center justify-between p-2.5 rounded bg-slate-900/80 border border-slate-800">
                    <div className="flex items-center gap-2">
                      <span className="w-10 text-center py-1 bg-indigo-950 text-indigo-300 font-bold rounded border border-indigo-800">
                        {fromNode}
                      </span>
                      <span className="text-slate-500">&rarr;</span>
                      <div className="flex flex-wrap gap-1.5">
                        {(toNodes || []).length > 0 ? (
                          toNodes.map((to, i) => (
                            <span key={i} className="px-2 py-0.5 bg-slate-800 text-slate-200 rounded border border-slate-700">
                              {to}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500 italic text-[11px]">No outgoing dependencies</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {!result.is_serializable && result.cycles.length > 0 && (
                <div className="mt-4 p-3 rounded bg-rose-950/60 border border-rose-800 text-xs font-mono text-rose-300">
                  <strong>Cycle Path:</strong> {result.cycles[0].join(' → ')}
                </div>
              )}
            </div>

            {/* Conflicting Pairs Table */}
            <div className="bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                <Repeat className="w-4 h-4 text-amber-400" />
                Detected Conflict Pairs ({result.conflicts.length})
              </h4>

              <div className="max-h-60 overflow-y-auto space-y-1.5 font-mono text-xs pr-1">
                {result.conflicts.length === 0 ? (
                  <div className="text-center py-8 text-slate-500">No conflicting pairs detected</div>
                ) : (
                  result.conflicts.map((c, i) => {
                    const badgeStyles = {
                      WR: 'text-amber-400 bg-amber-950/60 border-amber-800',
                      RW: 'text-indigo-400 bg-indigo-950/60 border-indigo-800',
                      WW: 'text-rose-400 bg-rose-950/60 border-rose-800',
                    };
                    return (
                      <div key={i} className="flex items-center justify-between p-2 rounded bg-slate-900/80 border border-slate-800/80">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded border ${badgeStyles[c.conflict_type] || 'text-slate-300'}`}>
                            {c.conflict_type}
                          </span>
                          <span className="text-cyan-300 font-bold">{c.key}</span>
                        </div>
                        <div className="text-slate-300 flex items-center gap-1.5 text-[11px]">
                          <span>{c.op1_str} ({c.from_txn})</span>
                          <span className="text-slate-500">&rarr;</span>
                          <span>{c.op2_str} ({c.to_txn})</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
