import React, { useState } from 'react';
import { 
  Play, 
  RotateCcw, 
  Plus, 
  Trash2, 
  Database, 
  FileText, 
  Cpu, 
  Clock,
  ArrowRight,
  Sliders,
  CheckCircle2,
  XCircle,
  AlertCircle,
  HelpCircle,
  Terminal,
  Activity
} from 'lucide-react';

export default function LiveControlRoom({ state, onRefresh, onNotify }) {
  const [protocol, setProtocol] = useState(state.protocol || '2PL');
  const [deadlockMode, setDeadlockMode] = useState(state.deadlock_mode || 'detection');
  const [victimPolicy, setVictimPolicy] = useState(state.victim_policy || 'youngest');
  const [preventionScheme, setPreventionScheme] = useState(state.prevention_scheme || 'wound_wait');
  
  // Custom Transaction Builder state
  const [manualTxnId, setManualTxnId] = useState('');
  const [operations, setOperations] = useState([
    { op_type: 'READ', key: 'A', value: '', duration: 0.05 },
    { op_type: 'WRITE', key: 'A', value: 150, duration: 0.05 },
  ]);
  const [submitting, setSubmitting] = useState(false);
  const [activeExperiment, setActiveExperiment] = useState(null);

  // Apply engine config
  const handleConfigChange = async (newProto, newMode, newScheme, newPolicy) => {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          protocol: newProto,
          deadlock_mode: newMode,
          prevention_scheme: newScheme,
          victim_policy: newPolicy,
        }),
      });
      if (res.ok) {
        onNotify(`Active configuration updated: ${newProto} [${newMode}]`, 'info');
        onRefresh();
      }
    } catch (err) {
      onNotify('Failed to update engine configuration', 'error');
    }
  };

  const handleReset = async () => {
    try {
      const res = await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          initial_storage: { A: 500, B: 500, C: 1000, X: 100, Y: 200 },
        }),
      });
      if (res.ok) {
        onNotify('Storage restored to initial seed; WAL & locks cleared', 'info');
        onRefresh();
      }
    } catch (err) {
      onNotify('Failed to reset system state', 'error');
    }
  };

  // Preset experiment scenarios
  const runPresetContention = async () => {
    setSubmitting(true);
    setActiveExperiment('contention');
    try {
      const txns = [
        {
          txn_id: 'Txn_DebitA',
          operations: [
            { op_type: 'READ', key: 'A', duration: 0.04 },
            { op_type: 'WRITE', key: 'A', value: 400, duration: 0.08 },
            { op_type: 'WRITE', key: 'B', value: 600, duration: 0.04 },
          ],
        },
        {
          txn_id: 'Txn_CreditB',
          operations: [
            { op_type: 'READ', key: 'A', duration: 0.06 },
            { op_type: 'WRITE', key: 'A', value: 450, duration: 0.04 },
            { op_type: 'WRITE', key: 'B', value: 550, duration: 0.04 },
          ],
        },
      ];
      await fetch('/api/transactions/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transactions: txns }),
      });
      onNotify('Launched Experiment EXP-01: High Contention Transfer', 'info');
      onRefresh();
    } catch (err) {
      onNotify('Failed to dispatch scenario', 'error');
    } finally {
      setTimeout(() => {
        setSubmitting(false);
        setActiveExperiment(null);
      }, 500);
    }
  };

  const runPresetDeadlock = async () => {
    setSubmitting(true);
    setActiveExperiment('deadlock');
    try {
      const txns = [
        {
          txn_id: 'Txn_Cross_1',
          operations: [
            { op_type: 'WRITE', key: 'A', value: 111, duration: 0.02 },
            { op_type: 'SLEEP', duration: 0.12 },
            { op_type: 'WRITE', key: 'B', value: 222, duration: 0.04 },
          ],
        },
        {
          txn_id: 'Txn_Cross_2',
          operations: [
            { op_type: 'WRITE', key: 'B', value: 333, duration: 0.02 },
            { op_type: 'SLEEP', duration: 0.12 },
            { op_type: 'WRITE', key: 'A', value: 444, duration: 0.04 },
          ],
        },
      ];
      await fetch('/api/transactions/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transactions: txns }),
      });
      onNotify('Launched Experiment EXP-02: Cyclic Cross-Lock Deadlock', 'warning');
      onRefresh();
    } catch (err) {
      onNotify('Failed to dispatch deadlock scenario', 'error');
    } finally {
      setTimeout(() => {
        setSubmitting(false);
        setActiveExperiment(null);
      }, 500);
    }
  };

  // Submit manual transaction
  const handleSubmitManual = async (e) => {
    e.preventDefault();
    if (operations.length === 0) return;
    setSubmitting(true);
    try {
      const formattedOps = operations.map(op => ({
        op_type: op.op_type,
        key: op.key || null,
        value: op.value !== '' ? (isNaN(op.value) ? op.value : Number(op.value)) : null,
        duration: Number(op.duration) || 0,
      }));

      const res = await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txn_id: manualTxnId.trim() || undefined,
          operations: formattedOps,
        }),
      });
      if (res.ok) {
        onNotify('Transaction queued to execution engine', 'success');
        setManualTxnId('');
        onRefresh();
      }
    } catch (err) {
      onNotify('Submission failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const addOperation = () => {
    setOperations([...operations, { op_type: 'READ', key: 'B', value: '', duration: 0.05 }]);
  };

  const removeOperation = (idx) => {
    setOperations(operations.filter((_, i) => i !== idx));
  };

  const updateOp = (idx, field, val) => {
    const next = [...operations];
    next[idx][field] = val;
    setOperations(next);
  };

  const transactions = state.transactions || [];
  const walRecords = state.wal_records || [];
  const storage = state.storage || {};

  return (
    <div className="space-y-8">
      {/* 1. Integrated System State & Engine Instrumentation Console */}
      <section className="bg-[#0b101b] border border-slate-800/80 rounded p-4 md:p-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-slate-800/60">
          <div>
            <span className="font-mono text-[10px] text-blue-400 tracking-wider uppercase block mb-0.5">
              Engine Parameters // Runtime Strategy
            </span>
            <h2 className="text-sm font-semibold text-white tracking-tight">
              Concurrency &amp; Conflict Resolution Architecture
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-mono border border-slate-700/70 transition"
              title="Re-seed in-memory storage, truncate WAL and clear lock tables"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Reset State</span>
            </button>
          </div>
        </div>

        {/* Control Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4">
          {/* Protocol Selection */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-mono text-slate-400 uppercase flex items-center gap-1.5">
              <span>Concurrency Protocol</span>
              <span title="The active serialization strategy applied across all worker threads" className="cursor-help">
                <HelpCircle className="w-3 h-3 text-slate-500" />
              </span>
            </label>
            <select
              value={protocol}
              onChange={(e) => {
                setProtocol(e.target.value);
                handleConfigChange(e.target.value, deadlockMode, preventionScheme, victimPolicy);
              }}
              className="w-full bg-[#111726] text-slate-100 text-xs font-mono rounded px-3 py-2 border border-slate-700/80 focus:outline-none focus:border-blue-500"
            >
              <option value="2PL">Strict 2PL (Strict Two-Phase Locking)</option>
              <option value="TO">Timestamp Ordering + Thomas Write Rule</option>
              <option value="OCC">Optimistic Concurrency Control (OCC)</option>
              <option value="MVCC">Multi-Version Concurrency Control (MVCC)</option>
            </select>
            <span className="text-[10px] text-slate-400 block font-mono">
              {protocol === '2PL' && 'Shared/Exclusive locks held until commit/abort'}
              {protocol === 'TO' && 'Read/write timestamps; late writes skipped (TWR)'}
              {protocol === 'OCC' && 'Private workspace; backward validation at commit'}
              {protocol === 'MVCC' && 'Multi-version chains; non-blocking snapshot reads'}
            </span>
          </div>

          {/* Deadlock Mode */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-mono text-slate-400 uppercase flex items-center gap-1.5">
              <span>Deadlock Mode</span>
              <span title="Detection uses background cycle search; prevention checks timestamps at lock time" className="cursor-help">
                <HelpCircle className="w-3 h-3 text-slate-500" />
              </span>
            </label>
            <select
              value={deadlockMode}
              onChange={(e) => {
                setDeadlockMode(e.target.value);
                handleConfigChange(protocol, e.target.value, preventionScheme, victimPolicy);
              }}
              className="w-full bg-[#111726] text-slate-100 text-xs font-mono rounded px-3 py-2 border border-slate-700/80 focus:outline-none focus:border-blue-500"
            >
              <option value="detection">Detection (Cycle Search DFS)</option>
              <option value="prevention">Prevention (Timestamp Order)</option>
            </select>
            <span className="text-[10px] text-slate-400 block font-mono">
              {deadlockMode === 'detection' ? 'Polls wait-for graph for cyclic dependencies' : 'Resolves conflicts at lock acquisition time'}
            </span>
          </div>

          {/* Victim Policy or Prevention Scheme */}
          {deadlockMode === 'detection' ? (
            <div className="space-y-1.5">
              <label className="text-[11px] font-mono text-slate-400 uppercase flex items-center gap-1.5">
                <span>Victim Selection Policy</span>
              </label>
              <select
                value={victimPolicy}
                onChange={(e) => {
                  setVictimPolicy(e.target.value);
                  handleConfigChange(protocol, deadlockMode, preventionScheme, e.target.value);
                }}
                className="w-full bg-[#111726] text-slate-100 text-xs font-mono rounded px-3 py-2 border border-slate-700/80 focus:outline-none focus:border-blue-500"
              >
                <option value="youngest">Youngest Transaction (Latest TS)</option>
                <option value="fewest_locks">Fewest Locks Held</option>
              </select>
              <span className="text-[10px] text-slate-400 block font-mono">
                {victimPolicy === 'youngest' ? 'Aborts highest-timestamp transaction' : 'Aborts txn holding minimum locked resources'}
              </span>
            </div>
          ) : (
            <div className="space-y-1.5">
              <label className="text-[11px] font-mono text-slate-400 uppercase flex items-center gap-1.5">
                <span>Prevention Scheme</span>
              </label>
              <select
                value={preventionScheme}
                onChange={(e) => {
                  setPreventionScheme(e.target.value);
                  handleConfigChange(protocol, deadlockMode, e.target.value, victimPolicy);
                }}
                className="w-full bg-[#111726] text-slate-100 text-xs font-mono rounded px-3 py-2 border border-slate-700/80 focus:outline-none focus:border-blue-500"
              >
                <option value="wound_wait">Wound-Wait (Preemptive)</option>
                <option value="wait_die">Wait-Die (Non-Preemptive)</option>
              </select>
              <span className="text-[10px] text-slate-400 block font-mono">
                {preventionScheme === 'wound_wait' ? 'Older wounds younger; younger waits' : 'Older waits; younger dies immediately'}
              </span>
            </div>
          )}

          {/* Engine Status Callout */}
          <div className="bg-[#0e1524] rounded p-3 border border-slate-800 flex flex-col justify-between">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-slate-400">STORAGE KEYS:</span>
              <span className="text-slate-200 font-bold">{Object.keys(storage).length} committed</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-slate-400">WAL RECORDS:</span>
              <span className="text-slate-200 font-bold">{walRecords.length} entries</span>
            </div>
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-slate-400">DEADLOCKS:</span>
              <span className={(state.deadlock_history || []).length > 0 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                {(state.deadlock_history || []).length} recorded
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Asymmetric Dual Console: Experiments (Left) & Custom Query Builder (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Predefined Experiments (5 cols) */}
        <section className="lg:col-span-5 bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-4">
          <div>
            <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
              Automated Workloads
            </span>
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Predefined Concurrency Experiments
            </h3>
            <p className="text-xs text-slate-400 mt-1 leading-relaxed">
              Curated workloads designed to demonstrate theoretical behaviors under thread interleavings.
            </p>
          </div>

          <div className="space-y-3">
            {/* Experiment 1 */}
            <div className="p-3.5 rounded bg-[#0e1524] border border-slate-800/80 hover:border-slate-700 transition">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-blue-950/70 text-blue-300 border border-blue-800/50">
                    EXP-01
                  </span>
                  <span className="text-xs font-medium text-slate-200">High Contention Transfer</span>
                </div>
                <button
                  onClick={runPresetContention}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-mono transition disabled:opacity-50"
                >
                  <Play className="w-3 h-3" />
                  <span>{activeExperiment === 'contention' ? 'Dispatching...' : 'Dispatch'}</span>
                </button>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
                <strong>Demonstrates:</strong> Lock queueing and serializable debit/credit between accounts A and B without lost updates.
              </p>
              <div className="mt-2 text-[10px] font-mono text-slate-400 flex items-center gap-3">
                <span>KEYS: A, B</span>
                <span>THREADS: 2</span>
                <span>RETRIES: Auto</span>
              </div>
            </div>

            {/* Experiment 2 */}
            <div className="p-3.5 rounded bg-[#0e1524] border border-slate-800/80 hover:border-slate-700 transition">
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-rose-950/70 text-rose-300 border border-rose-800/50">
                    EXP-02
                  </span>
                  <span className="text-xs font-medium text-slate-200">Cyclic Cross-Lock Deadlock</span>
                </div>
                <button
                  onClick={runPresetDeadlock}
                  disabled={submitting}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-mono transition disabled:opacity-50"
                >
                  <Play className="w-3 h-3" />
                  <span>{activeExperiment === 'deadlock' ? 'Triggering...' : 'Trigger'}</span>
                </button>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
                <strong>Demonstrates:</strong> T1 holds A, requests B; T2 holds B, requests A. Triggers cycle detection, victim abort &amp; retry.
              </p>
              <div className="mt-2 text-[10px] font-mono text-slate-400 flex items-center gap-3">
                <span>CYCLE: T1 &harr; T2</span>
                <span>VICTIM: Swappable</span>
              </div>
            </div>
          </div>
        </section>

        {/* Custom Transaction Workspace (7 cols) */}
        <section className="lg:col-span-7 bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
                Transaction Composition
              </span>
              <h3 className="text-sm font-semibold text-white tracking-tight">
                Custom Transaction Studio
              </h3>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 font-mono">TXN_ID:</span>
              <input
                type="text"
                placeholder="Auto-generated (T1, T2...)"
                value={manualTxnId}
                onChange={(e) => setManualTxnId(e.target.value)}
                className="w-48 bg-[#111726] text-xs text-slate-200 rounded px-2.5 py-1 border border-slate-700/80 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>
          </div>

          {/* Operation sequence editor */}
          <form onSubmit={handleSubmitManual} className="space-y-3">
            <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
              {operations.map((op, idx) => (
                <div key={idx} className="flex items-center gap-2 bg-[#0e1524] p-2 rounded border border-slate-800 text-xs font-mono">
                  <span className="text-slate-400 w-6 text-center text-[10px]">
                    #{String(idx + 1).padStart(2, '0')}
                  </span>

                  <select
                    value={op.op_type}
                    onChange={(e) => updateOp(idx, 'op_type', e.target.value)}
                    className="bg-[#141d2e] text-slate-200 text-xs font-mono font-bold rounded px-2 py-1 border border-slate-700"
                  >
                    <option value="READ">READ</option>
                    <option value="WRITE">WRITE</option>
                    <option value="SLEEP">SLEEP</option>
                  </select>

                  {op.op_type !== 'SLEEP' ? (
                    <>
                      <input
                        type="text"
                        placeholder="Key"
                        value={op.key || ''}
                        onChange={(e) => updateOp(idx, 'key', e.target.value)}
                        className="w-20 bg-[#141d2e] text-cyan-300 text-xs font-mono rounded px-2 py-1 border border-slate-700"
                        required
                      />
                      {op.op_type === 'WRITE' && (
                        <input
                          type="text"
                          placeholder="Value"
                          value={op.value ?? ''}
                          onChange={(e) => updateOp(idx, 'value', e.target.value)}
                          className="flex-1 bg-[#141d2e] text-slate-200 text-xs font-mono rounded px-2 py-1 border border-slate-700"
                          required
                        />
                      )}
                    </>
                  ) : (
                    <span className="flex-1 text-[11px] text-slate-400 font-sans italic">
                      Interleaving delay to provoke race conditions
                    </span>
                  )}

                  <div className="flex items-center gap-1 text-slate-400 text-[11px]">
                    <Clock className="w-3 h-3 text-slate-500" />
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      max="2"
                      value={op.duration}
                      onChange={(e) => updateOp(idx, 'duration', e.target.value)}
                      className="w-14 bg-[#141d2e] text-slate-300 text-xs rounded px-1.5 py-1 border border-slate-700 text-center font-mono"
                    />
                    <span>s</span>
                  </div>

                  {operations.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeOperation(idx)}
                      className="text-slate-400 hover:text-rose-400 transition p-1"
                      title="Remove step"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
              <button
                type="button"
                onClick={addOperation}
                className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-mono transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Operation</span>
              </button>

              <button
                type="submit"
                disabled={submitting}
                className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold rounded shadow transition disabled:opacity-50"
              >
                <Play className="w-3.5 h-3.5" />
                <span>{submitting ? 'Executing...' : 'Execute Transaction'}</span>
              </button>
            </div>
          </form>
        </section>
      </div>

      {/* 3. Transaction Activity Monitor (Clean Semantic States) */}
      <section className="bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800/60">
          <div>
            <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
              Transaction Lifecycle
            </span>
            <h3 className="text-sm font-semibold text-white tracking-tight">
              Active &amp; Historical Transaction Monitor
            </h3>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span> Running
            </span>
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-amber-400"></span> Blocked
            </span>
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span> Committed
            </span>
            <span className="flex items-center gap-1.5 text-slate-300">
              <span className="w-2 h-2 rounded-full bg-rose-400"></span> Aborted
            </span>
          </div>
        </div>

        {transactions.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs font-mono">
            No transactions in engine queue. Launch an experiment or submit a transaction above to observe live state.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 max-h-80 overflow-y-auto pr-1">
            {transactions.slice().reverse().map((tx) => {
              const statusBadge = {
                RUNNING: 'text-blue-400 border-blue-800/60 bg-blue-950/40',
                WAITING: 'text-amber-400 border-amber-800/60 bg-amber-950/40',
                COMMITTED: 'text-emerald-400 border-emerald-800/60 bg-emerald-950/40',
                ABORTED: 'text-rose-400 border-rose-800/60 bg-rose-950/40',
                RETRYING: 'text-purple-400 border-purple-800/60 bg-purple-950/40',
                NEW: 'text-slate-400 border-slate-700 bg-slate-800/40',
              }[tx.status] || 'text-slate-400 border-slate-700 bg-slate-800/40';

              const progress = tx.total_ops > 0 ? Math.min(100, Math.round((tx.current_op_index / tx.total_ops) * 100)) : 100;

              return (
                <div key={tx.txn_id} className="p-3 rounded bg-[#0e1422] border border-slate-800 flex flex-col justify-between space-y-2.5 font-mono text-xs">
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-white tracking-wide">{tx.txn_id}</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded border uppercase font-bold tracking-wider ${statusBadge}`}>
                        {tx.status}
                      </span>
                    </div>

                    {/* Progress tracking line */}
                    <div className="w-full bg-slate-800/80 h-1 rounded mt-2 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-300 ${
                          tx.status === 'COMMITTED' ? 'bg-emerald-500' :
                          tx.status === 'ABORTED' ? 'bg-rose-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${tx.status === 'COMMITTED' ? 100 : progress}%` }}
                      ></div>
                    </div>
                  </div>

                  <div className="text-[11px] text-slate-400 space-y-1">
                    <div className="flex justify-between">
                      <span>Operations:</span>
                      <span className="text-slate-200">{tx.current_op_index} / {tx.total_ops}</span>
                    </div>
                    {tx.retry_count > 0 && (
                      <div className="flex justify-between text-purple-300">
                        <span>Retry Count:</span>
                        <span className="font-bold">{tx.retry_count}</span>
                      </div>
                    )}
                    {Object.keys(tx.read_values || {}).length > 0 && (
                      <div className="flex justify-between">
                        <span>Observed:</span>
                        <span className="text-slate-300">
                          {Object.entries(tx.read_values).map(([k, v]) => `${k}=${v}`).join(', ')}
                        </span>
                      </div>
                    )}
                  </div>

                  {tx.abort_reason && (
                    <div className="text-[10px] text-rose-300/90 pt-1.5 border-t border-slate-800/80 truncate" title={tx.abort_reason}>
                      Abort: {tx.abort_reason}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4. Dual Telemetry: Storage Engine (Left) & Write-Ahead Log Stream (Right) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Committed Storage State (5 cols) */}
        <section className="lg:col-span-5 bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/60">
            <div>
              <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
                Primary Store
              </span>
              <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                <Database className="w-4 h-4 text-cyan-400" />
                In-Memory Storage State
              </h3>
            </div>
            <span className="text-[10px] font-mono text-slate-400">Thread-Safe Dict</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-[#0e1422] text-slate-400 uppercase text-[10px] border-b border-slate-800">
                <tr>
                  <th className="py-2 px-3">Key</th>
                  <th className="py-2 px-3">Committed Value</th>
                  <th className="py-2 px-3 text-right">Datatype</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {Object.keys(storage).length === 0 ? (
                  <tr>
                    <td colSpan={3} className="py-8 text-center text-slate-400 text-xs">
                      Storage is unpopulated or volatile RAM has been cleared.
                    </td>
                  </tr>
                ) : (
                  Object.entries(storage).map(([key, val]) => (
                    <tr key={key} className="hover:bg-slate-900/50 transition">
                      <td className="py-2 px-3 font-bold text-cyan-300">{key}</td>
                      <td className="py-2 px-3 text-slate-100 font-bold">{JSON.stringify(val)}</td>
                      <td className="py-2 px-3 text-right text-slate-400 text-[10px]">{typeof val}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Write-Ahead Log Stream (7 cols) */}
        <section className="lg:col-span-7 bg-[#0b101b] border border-slate-800/80 rounded p-5 space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800/60">
            <div>
              <span className="font-mono text-[10px] text-slate-400 tracking-wider uppercase block">
                Append-Only Persistence
              </span>
              <h3 className="text-sm font-semibold text-white tracking-tight flex items-center gap-2">
                <FileText className="w-4 h-4 text-amber-400" />
                Write-Ahead Log (WAL) Stream
              </h3>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-300 border border-emerald-800/60">
              Synchronous fsync()
            </span>
          </div>

          <div className="max-h-72 overflow-y-auto space-y-1.5 font-mono text-xs pr-1">
            {walRecords.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-xs">WAL log buffer is currently empty.</div>
            ) : (
              walRecords.slice().reverse().map((rec) => {
                const opColor = {
                  BEGIN: 'text-blue-400 bg-blue-950/60 border-blue-800/60',
                  WRITE: 'text-amber-400 bg-amber-950/60 border-amber-800/60',
                  COMMIT: 'text-emerald-400 bg-emerald-950/60 border-emerald-800/60',
                  ABORT: 'text-rose-400 bg-rose-950/60 border-rose-800/60',
                  CLR: 'text-purple-400 bg-purple-950/60 border-purple-800/60',
                }[rec.op_type] || 'text-slate-400 border-slate-700 bg-slate-800';

                return (
                  <div key={rec.lsn} className="flex items-center justify-between p-2 rounded bg-[#0e1422] border border-slate-800/70 text-[11px]">
                    <div className="flex items-center gap-2.5">
                      <span className="text-slate-400 w-12 font-bold">#{String(rec.lsn).padStart(4, '0')}</span>
                      <span className="text-slate-200 font-bold w-24 truncate">{rec.txn_id}</span>
                      <span className={`px-1.5 py-0.5 text-[9px] font-bold rounded border uppercase tracking-wider ${opColor}`}>
                        {rec.op_type}
                      </span>
                    </div>

                    {rec.op_type === 'WRITE' && (
                      <div className="text-right text-slate-300 flex items-center gap-1.5 text-[11px]">
                        <span className="text-cyan-300 font-bold">{rec.key}</span>
                        <span className="text-slate-400 line-through">{rec.old_value ?? 'NULL'}</span>
                        <ArrowRight className="w-3 h-3 text-slate-500 inline" />
                        <span className="text-emerald-300 font-bold">{rec.new_value}</span>
                      </div>
                    )}

                    {rec.op_type === 'CLR' && (
                      <div className="text-right text-purple-300 text-[10px]">
                        CLR: Undid write on {rec.key} &rarr; restored {rec.new_value}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
