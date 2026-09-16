import React, { useState } from 'react';
import { 
  ShieldCheck, 
  Play, 
  ArrowRight, 
  CheckCircle2, 
  XCircle, 
  HelpCircle,
  Clock,
  Check,
  X
} from 'lucide-react';

export default function IsolationPlayground({ onNotify }) {
  const [selectedScenario, setSelectedScenario] = useState('dirty_read');
  const [isolationLevel, setIsolationLevel] = useState('READ_COMMITTED');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const scenarios = [
    {
      id: 'dirty_read',
      name: 'Dirty Read (G1)',
      description: 'Transaction reads uncommitted dirty changes from a transaction that later aborts.',
      permittedAt: ['READ_UNCOMMITTED'],
    },
    {
      id: 'non_repeatable_read',
      name: 'Non-Repeatable Read (G2a)',
      description: 'Transaction re-reads the same row and retrieves modified committed values.',
      permittedAt: ['READ_UNCOMMITTED', 'READ_COMMITTED'],
    },
    {
      id: 'lost_update',
      name: 'Lost Update (GLU)',
      description: 'Concurrent transactions read the same data and overwrite each other silently.',
      permittedAt: ['READ_UNCOMMITTED', 'READ_COMMITTED'],
    },
    {
      id: 'phantom_read',
      name: 'Phantom Read (A3)',
      description: 'Concurrent insert satisfies predicate query on re-read.',
      permittedAt: ['READ_UNCOMMITTED', 'READ_COMMITTED', 'REPEATABLE_READ'],
    },
  ];

  const levels = [
    { id: 'READ_UNCOMMITTED', label: 'Read Uncommitted', code: 'RU' },
    { id: 'READ_COMMITTED', label: 'Read Committed', code: 'RC' },
    { id: 'REPEATABLE_READ', label: 'Repeatable Read', code: 'RR' },
    { id: 'SERIALIZABLE', label: 'Serializable', code: 'SER' },
  ];

  const handleRunScenario = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/isolation/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario: selectedScenario,
          isolation_level: isolationLevel,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        if (data.anomaly_occurred) {
          onNotify(`Anomaly '${data.anomaly_name}' occurred under ${isolationLevel}`, 'warning');
        } else {
          onNotify(`Anomaly '${data.anomaly_name}' was prevented under ${isolationLevel}`, 'success');
        }
      }
    } catch (err) {
      onNotify('Failed to execute experiment', 'error');
    } finally {
      setLoading(false);
    }
  };

  const currentScenarioObj = scenarios.find((s) => s.id === selectedScenario);
  const isTheoreticallyPermitted = currentScenarioObj?.permittedAt.includes(isolationLevel);

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-[#0b101b] border border-slate-800/80 rounded p-4 md:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="font-mono text-[10px] text-blue-400 tracking-wider uppercase block mb-0.5">
            Empirical Anomaly Laboratory
          </span>
          <h2 className="text-sm font-semibold text-white tracking-tight">
            ANSI SQL Isolation Levels &amp; Concurrency Anomalies
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Test whether Dirty Reads, Non-Repeatable Reads, Lost Updates, and Phantom Reads manifest under weaker isolation vs full serial consistency.
          </p>
        </div>
      </div>

      {/* 1. Academic Theory Matrix */}
      <div className="bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
            Academic Reference Matrix (ANSI SQL Standard)
          </span>
          <span className="text-[10px] font-mono text-slate-400">Click any cell to configure experiment</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs border border-slate-800">
            <thead className="bg-[#0e1422] text-slate-400 uppercase text-[10px] border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Concurrency Anomaly</th>
                {levels.map((lvl) => (
                  <th key={lvl.id} className="py-2.5 px-3 text-center">
                    {lvl.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {scenarios.map((sc) => (
                <tr key={sc.id} className={selectedScenario === sc.id ? 'bg-blue-950/20' : 'hover:bg-slate-900/40'}>
                  <td className="py-2.5 px-3">
                    <button
                      onClick={() => {
                        setSelectedScenario(sc.id);
                        setResult(null);
                      }}
                      className="text-left font-semibold text-slate-200 hover:text-blue-400"
                    >
                      {sc.name}
                    </button>
                    <span className="block text-[10px] text-slate-400 font-sans">{sc.description}</span>
                  </td>
                  {levels.map((lvl) => {
                    const permitted = sc.permittedAt.includes(lvl.id);
                    const isSelected = selectedScenario === sc.id && isolationLevel === lvl.id;
                    return (
                      <td
                        key={lvl.id}
                        onClick={() => {
                          setSelectedScenario(sc.id);
                          setIsolationLevel(lvl.id);
                          setResult(null);
                        }}
                        className={`py-2.5 px-3 text-center cursor-pointer transition ${
                          isSelected ? 'bg-blue-900/40 border border-blue-600' : ''
                        }`}
                      >
                        {permitted ? (
                          <span className="inline-flex items-center gap-1 text-rose-400 text-[11px] font-bold">
                            <X className="w-3 h-3" /> Permitted
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px] font-bold">
                            <Check className="w-3 h-3" /> Prevented
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 2. Experiment Setup & Execution Trigger */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Controls (4 cols) */}
        <div className="lg:col-span-4 bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-4 font-mono text-xs">
          <div>
            <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block mb-1">
              Active Parameters
            </span>
            <h3 className="text-xs font-semibold text-white tracking-tight uppercase">
              Experiment Configuration
            </h3>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] text-slate-400 uppercase block">Selected Anomaly:</label>
            <select
              value={selectedScenario}
              onChange={(e) => {
                setSelectedScenario(e.target.value);
                setResult(null);
              }}
              className="w-full bg-[#111726] text-slate-200 text-xs rounded px-2.5 py-2 border border-slate-700"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-[10px] text-slate-400 uppercase block">Isolation Level:</label>
            <select
              value={isolationLevel}
              onChange={(e) => {
                setIsolationLevel(e.target.value);
                setResult(null);
              }}
              className="w-full bg-[#111726] text-slate-200 text-xs rounded px-2.5 py-2 border border-slate-700"
            >
              {levels.map((l) => (
                <option key={l.id} value={l.id}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Theoretical Expectation Box */}
          <div className="p-3 rounded bg-[#0e1422] border border-slate-800 text-[11px] font-sans leading-relaxed">
            <strong className="text-slate-200 block mb-1 font-mono uppercase text-[10px]">
              Theoretical Hypothesis:
            </strong>
            Under <strong className="text-white font-mono">{isolationLevel}</strong>, the{' '}
            <strong className="text-white">{currentScenarioObj?.name}</strong> anomaly is{' '}
            {isTheoreticallyPermitted ? (
              <span className="text-rose-400 font-bold font-mono">EXPECTED TO OCCUR</span>
            ) : (
              <span className="text-emerald-400 font-bold font-mono">EXPECTED TO BE PREVENTED</span>
            )}.
          </div>

          <button
            onClick={handleRunScenario}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold rounded shadow transition disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{loading ? 'Simulating Interleaving...' : 'Execute Experiment'}</span>
          </button>
        </div>

        {/* 3. Results & Step-by-Step Interleaving Timeline (8 cols) */}
        <div className="lg:col-span-8 space-y-4">
          {result ? (
            <div className="bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-5">
              {/* Verdict Header */}
              <div className="flex items-center justify-between pb-4 border-b border-slate-800/70">
                <div className="flex items-center gap-3">
                  {result.anomaly_occurred ? (
                    <XCircle className="w-6 h-6 text-rose-500 flex-shrink-0" />
                  ) : (
                    <CheckCircle2 className="w-6 h-6 text-emerald-400 flex-shrink-0" />
                  )}
                  <div>
                    <h4 className="text-sm font-bold text-white font-mono">
                      {result.anomaly_occurred ? (
                        <span className="text-rose-400">ANOMALY OBSERVED: {result.anomaly_name}</span>
                      ) : (
                        <span className="text-emerald-400">CONSISTENCY PRESERVED: {result.anomaly_name} PREVENTED</span>
                      )}
                    </h4>
                    <span className="text-[11px] text-slate-400 font-mono">
                      Executed at level {result.isolation_level}
                    </span>
                  </div>
                </div>

                <span className={`px-2 py-0.5 text-[10px] font-mono font-bold rounded border uppercase ${
                  result.anomaly_occurred 
                    ? 'bg-rose-950/60 text-rose-300 border-rose-800' 
                    : 'bg-emerald-950/60 text-emerald-300 border-emerald-800'
                }`}>
                  {result.anomaly_occurred ? 'VULNERABLE' : 'PROTECTED'}
                </span>
              </div>

              {/* Explanation */}
              <div className="p-3.5 rounded bg-[#0e1422] border border-slate-800 text-xs text-slate-300 font-sans leading-relaxed">
                <strong className="text-blue-400 font-mono text-[10px] uppercase block mb-1">
                  DBMS Internal Mechanics:
                </strong>
                {result.explanation}
              </div>

              {/* Execution Interleaving Timeline */}
              <div>
                <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block mb-2">
                  Chronological Operation Interleaving (T1 &amp; T2)
                </span>

                <div className="space-y-1.5 font-mono text-xs">
                  {result.timeline.map((step) => (
                    <div
                      key={step.step}
                      className={`p-2.5 rounded border flex items-center justify-between text-[11px] ${
                        step.anomaly
                          ? 'bg-rose-950/70 border-rose-700 text-rose-200'
                          : 'bg-[#0e1422] border-slate-800/80 text-slate-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-slate-400 w-5">#{step.step}</span>
                        <span className="px-1.5 py-0.5 rounded bg-[#131b2e] border border-slate-700 text-blue-300 font-bold">
                          {step.txn}
                        </span>
                        <span className="font-bold text-slate-100">{step.action}</span>
                      </div>
                      <span className="text-slate-400 text-[10px] font-sans max-w-sm text-right">
                        {step.detail}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#0b101b] border border-slate-800/80 rounded p-12 text-center text-slate-400 font-mono text-xs">
              Select an anomaly and isolation level, then click "Execute Experiment" to run the schedule and view the interleaving trace.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
