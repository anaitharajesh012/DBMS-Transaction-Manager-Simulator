import React, { useState } from 'react';
import { 
  Skull, 
  RotateCcw, 
  Play, 
  CheckCircle2, 
  AlertOctagon, 
  ArrowRight, 
  FileText, 
  ShieldCheck,
  Zap
} from 'lucide-react';

export default function ChaosRecovery({ state, onRefresh, onNotify }) {
  const [crashState, setCrashState] = useState(null);
  const [recoveryReport, setRecoveryReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(0); // 1: Analysis, 2: Redo, 3: Undo

  // 1. Launch in-flight dirty workload then trigger crash
  const handleChaosCrash = async () => {
    setLoading(true);
    setRecoveryReport(null);
    try {
      // Submit a winning transaction that commits
      await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txn_id: 'Txn_Committed_Winner',
          operations: [
            { op_type: 'WRITE', key: 'A', value: 888, duration: 0.02 },
          ],
        }),
      });

      // Submit an in-flight uncommitted transaction with a delay
      await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          txn_id: 'Txn_InFlight_Loser',
          operations: [
            { op_type: 'WRITE', key: 'B', value: 9999, duration: 0.5 },
          ],
        }),
      });

      // Wait a moment for writes to reach WAL & storage, then immediately crash!
      setTimeout(async () => {
        const res = await fetch('/api/crash', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          setCrashState(data);
          onNotify('CRASH! Volatile memory wiped. WAL persisted on disk.', 'error');
          onRefresh();
        }
        setLoading(false);
      }, 100);
    } catch (err) {
      onNotify('Chaos simulation failed', 'error');
      setLoading(false);
    }
  };

  // 2. Trigger ARIES-lite Recovery
  const handleRunRecovery = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/recover', { method: 'POST' });
      if (res.ok) {
        const report = await res.json();
        setRecoveryReport(report);
        setActiveStep(1);
        onNotify('ARIES-Lite 3-Pass Recovery Executed Successfully!', 'success');
        onRefresh();
      }
    } catch (err) {
      onNotify('Recovery failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <AlertOctagon className="w-5 h-5 text-rose-400" />
          <h2 className="text-lg font-bold text-slate-100">Chaos Testing & ARIES-Lite Crash Recovery</h2>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Simulate sudden power cuts or engine crashes mid-execution. Volatile RAM is completely erased while the on-disk Write-Ahead Log (WAL) survives. Run genuine ARIES-lite 3-pass recovery (Analysis, Redo, Undo) to reconstruct a consistent, uncorrupted database state.
        </p>
      </div>

      {/* Action Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Crash Trigger Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <Skull className="w-5 h-5 text-rose-500" />
              <h3 className="text-base font-bold text-slate-100">1. Simulate Mid-Flight Crash</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Dispatches committed and in-flight transactions, then triggers an abrupt crash. In-memory data is instantly erased, simulating power loss before in-flight transactions commit.
            </p>
          </div>

          <button
            onClick={handleChaosCrash}
            disabled={loading}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-rose-600/30 transition disabled:opacity-50"
          >
            <Zap className="w-4 h-4" />
            Launch Chaos Workload & Crash
          </button>
        </div>

        {/* Recovery Trigger Card */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <RotateCcw className="w-5 h-5 text-emerald-400" />
              <h3 className="text-base font-bold text-slate-100">2. Run ARIES 3-Pass Recovery</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Replays the physical WAL log from disk. Analysis pass identifies winners and losers; Redo pass repeats history; Undo pass rolls back uncommitted loser writes using recorded old values and Compensation Log Records (CLRs).
            </p>
          </div>

          <button
            onClick={handleRunRecovery}
            disabled={loading}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-emerald-600/30 transition disabled:opacity-50"
          >
            <Play className="w-4 h-4" />
            Trigger ARIES Recovery
          </button>
        </div>
      </div>

      {/* Crash Status Notification */}
      {crashState && !recoveryReport && (
        <div className="bg-rose-950/70 border border-rose-800 rounded-xl p-5 shadow-xl">
          <div className="flex items-center gap-3 mb-2">
            <Skull className="w-6 h-6 text-rose-400 animate-pulse" />
            <h3 className="text-sm font-bold text-rose-200">System Crashed! Volatile Storage Wiped</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono mt-3">
            <div className="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span className="text-slate-400 block mb-1">Pre-Crash Storage:</span>
              <span className="text-cyan-300 font-bold">{JSON.stringify(crashState.pre_crash_storage)}</span>
            </div>
            <div className="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span className="text-slate-400 block mb-1">In-Flight Loser Transactions:</span>
              <span className="text-rose-400 font-bold">{crashState.active_in_flight_txns.join(', ') || 'None in flight'}</span>
            </div>
            <div className="bg-slate-900/80 p-3 rounded border border-slate-800">
              <span className="text-slate-400 block mb-1">On-Disk WAL Status:</span>
              <span className="text-emerald-400 font-bold">100% INTACT & FLUSHED</span>
            </div>
          </div>
        </div>
      )}

      {/* ARIES 3-Pass Recovery Playback */}
      {recoveryReport && (
        <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <ShieldCheck className="w-7 h-7 text-emerald-400" />
              <div>
                <h3 className="text-base font-bold text-slate-100">
                  ARIES Recovery Results & State Reconstruction
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Three genuine passes executed strictly against the on-disk WAL.
                </p>
              </div>
            </div>

            {/* Step navigation tabs */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveStep(1)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition ${
                  activeStep === 1
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                Pass 1: Analysis
              </button>
              <button
                onClick={() => setActiveStep(2)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition ${
                  activeStep === 2
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                Pass 2: Redo
              </button>
              <button
                onClick={() => setActiveStep(3)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition ${
                  activeStep === 3
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                Pass 3: Undo
              </button>
            </div>
          </div>

          {/* Phase 1: Analysis Pass Content */}
          {activeStep === 1 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Phase 1: Analysis Pass (Determining Winners & Losers)
                </h4>
                <div className="flex gap-3 text-xs font-mono">
                  <span className="text-emerald-400 font-bold">Winners: {recoveryReport.winners.join(', ') || 'None'}</span>
                  <span className="text-rose-400 font-bold">Losers: {recoveryReport.losers.join(', ') || 'None'}</span>
                </div>
              </div>

              <div className="max-h-60 overflow-y-auto space-y-2 font-mono text-xs pr-1">
                {recoveryReport.analysis_steps.map((step, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500 w-12">LSN #{step.lsn}</span>
                      <span className="font-bold text-slate-200">{step.txn_id}</span>
                    </div>
                    <span className="text-slate-400 text-[11px]">{step.event}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Phase 2: Redo Pass Content */}
          {activeStep === 2 && (
            <div className="space-y-4">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Phase 2: Redo Pass (Repeating History Forward to Crash Point)
              </h4>

              <div className="max-h-60 overflow-y-auto space-y-2 font-mono text-xs pr-1">
                {recoveryReport.redo_steps.map((step, idx) => (
                  <div key={idx} className="p-2.5 rounded bg-slate-950/70 border border-slate-800 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className="text-slate-500 w-12">LSN #{step.lsn}</span>
                      <span className="font-bold text-slate-200">{step.txn_id}</span>
                      <span className="text-cyan-300 font-bold">{step.key} = {step.value_applied}</span>
                    </div>
                    <span className="text-emerald-400 text-[11px]">{step.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Phase 3: Undo Pass Content */}
          {activeStep === 3 && (
            <div className="space-y-4">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Phase 3: Undo Pass (Rolling Back Loser Transactions with CLRs)
              </h4>

              <div className="max-h-60 overflow-y-auto space-y-2 font-mono text-xs pr-1">
                {recoveryReport.undo_steps.length === 0 ? (
                  <div className="text-center py-6 text-slate-500">No loser transactions required undo</div>
                ) : (
                  recoveryReport.undo_steps.map((step, idx) => (
                    <div key={idx} className="p-2.5 rounded bg-rose-950/40 border border-rose-900/60 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-slate-400 w-12">LSN #{step.undone_lsn}</span>
                        <span className="font-bold text-rose-300">{step.txn_id}</span>
                        <span className="text-slate-200">{step.action}</span>
                      </div>
                      <span className="text-purple-400 text-[11px]">CLR LSN #{step.clr_lsn}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {/* Final Reconstructed Storage Diff */}
          <div className="pt-4 border-t border-slate-800">
            <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
              Reconstructed Consistent Storage Snapshot
            </h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-mono text-xs">
              {Object.entries(recoveryReport.final_storage).map(([k, v]) => (
                <div key={k} className="bg-slate-950 p-3 rounded-lg border border-slate-800 flex justify-between items-center">
                  <span className="text-cyan-300 font-bold">{k}:</span>
                  <span className="text-white font-bold text-sm">{JSON.stringify(v)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
