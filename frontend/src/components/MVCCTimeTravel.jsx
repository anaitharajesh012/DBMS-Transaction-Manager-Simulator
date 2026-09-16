import React, { useEffect, useState } from 'react';
import { 
  History, 
  Clock, 
  Layers, 
  Search, 
  ArrowRight, 
  GitBranch, 
  CheckCircle2, 
  Plus,
  Play
} from 'lucide-react';

export default function MVCCTimeTravel({ state, onRefresh, onNotify }) {
  const isMVCC = state.protocol === 'MVCC';
  const [versionChains, setVersionChains] = useState({});
  const [selectedKey, setSelectedKey] = useState('A');
  const [targetTimestamp, setTargetTimestamp] = useState(0);
  const [timeTravelResult, setTimeTravelResult] = useState(null);
  const [loading, setLoading] = useState(false);

  // New update helper
  const [newUpdateVal, setNewUpdateVal] = useState('');

  const fetchChains = async () => {
    if (!isMVCC) return;
    try {
      const res = await fetch('/api/mvcc/versions');
      if (res.ok) {
        const data = await res.json();
        setVersionChains(data.version_chains || {});
        const keys = Object.keys(data.version_chains || {});
        if (keys.length > 0 && !keys.includes(selectedKey)) {
          setSelectedKey(keys[0]);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchChains();
  }, [state.protocol]);

  const handleActivateMVCC = async () => {
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ protocol: 'MVCC' }),
      });
      if (res.ok) {
        onNotify('Switched protocol to Multi-Version Concurrency Control (MVCC)', 'success');
        onRefresh();
      }
    } catch (err) {
      onNotify('Failed to switch protocol', 'error');
    }
  };

  const handleTimeTravelQuery = async () => {
    if (!selectedKey) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/mvcc/time-travel?key=${selectedKey}&timestamp=${targetTimestamp}`);
      if (res.ok) {
        const data = await res.json();
        setTimeTravelResult(data);
      }
    } catch (err) {
      onNotify('Time-travel query failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCommitNewVersion = async (e) => {
    e.preventDefault();
    if (!newUpdateVal.trim()) return;
    try {
      const val = isNaN(newUpdateVal) ? newUpdateVal : Number(newUpdateVal);
      await fetch('/api/transactions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          operations: [
            { op_type: 'WRITE', key: selectedKey, value: val, duration: 0.05 },
          ],
        }),
      });
      onNotify(`Committed new version for key '${selectedKey}' = ${val}`, 'info');
      setNewUpdateVal('');
      onRefresh();
      setTimeout(fetchChains, 200);
    } catch (err) {
      onNotify('Failed to commit version', 'error');
    }
  };

  const currentChain = versionChains[selectedKey] || [];
  const minTs = currentChain.length > 0 ? Math.min(...currentChain.map(v => v.created_ts)) : 0;
  const maxTs = currentChain.length > 0 ? Math.max(...currentChain.map(v => v.created_ts)) : 100;

  return (
    <div className="space-y-6">
      {/* Non-MVCC Alert Banner */}
      {!isMVCC && (
        <div className="bg-amber-950/70 border border-amber-700/80 rounded-xl p-5 shadow-lg flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Layers className="w-6 h-6 text-amber-400 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-bold text-amber-200">MVCC Protocol is Not Currently Active</h3>
              <p className="text-xs text-amber-300/80 mt-0.5">
                Time-travel queries require version chains maintained exclusively under the Multi-Version Concurrency Control protocol.
              </p>
            </div>
          </div>
          <button
            onClick={handleActivateMVCC}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-indigo-600/30 transition"
          >
            Activate MVCC Now
          </button>
        </div>
      )}

      {/* Header Info */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <History className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-slate-100">MVCC Time-Travel & Snapshot Isolation Inspector</h2>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Under MVCC, write operations create append-only timestamped versions rather than overwriting data in-place. Readers observe consistent snapshots without ever blocking writers. Scrub across logical timestamps below to inspect historical database states.
        </p>
      </div>

      {isMVCC && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Key Selector & Historical Query */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-5">
            <div>
              <label className="block text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
                1. Select Data Key
              </label>
              <select
                value={selectedKey}
                onChange={(e) => {
                  setSelectedKey(e.target.value);
                  setTimeTravelResult(null);
                }}
                className="w-full bg-slate-950 text-sm font-mono text-cyan-300 font-bold rounded-lg px-3 py-2 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                {Object.keys(versionChains).length === 0 ? (
                  <option value="">No version chains available</option>
                ) : (
                  Object.keys(versionChains).map((k) => (
                    <option key={k} value={k}>{k} ({versionChains[k]?.length} versions)</option>
                  ))
                )}
              </select>
            </div>

            {/* Time Travel Query Scrubbing */}
            <div className="space-y-3 pt-3 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  2. Query AS OF Timestamp
                </label>
                <span className="font-mono text-xs text-indigo-300 font-bold bg-indigo-950/70 px-2 py-0.5 rounded border border-indigo-800">
                  t = {Number(targetTimestamp).toFixed(2)}
                </span>
              </div>

              <input
                type="range"
                min={minTs}
                max={maxTs + 10}
                step={(maxTs - minTs) > 0 ? (maxTs - minTs) / 50 : 1}
                value={targetTimestamp}
                onChange={(e) => {
                  setTargetTimestamp(Number(e.target.value));
                  handleTimeTravelQuery();
                }}
                className="w-full accent-indigo-500 cursor-pointer"
              />

              <div className="flex gap-2">
                <input
                  type="number"
                  step="0.01"
                  value={targetTimestamp}
                  onChange={(e) => setTargetTimestamp(Number(e.target.value))}
                  placeholder="Target Timestamp"
                  className="flex-1 bg-slate-950 text-xs font-mono text-slate-200 px-3 py-2 rounded-lg border border-slate-700"
                />
                <button
                  onClick={handleTimeTravelQuery}
                  disabled={loading}
                  className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg shadow transition disabled:opacity-50"
                >
                  <Search className="w-3.5 h-3.5" />
                  Query
                </button>
              </div>
            </div>

            {/* Quick Commit Version Helper */}
            <form onSubmit={handleCommitNewVersion} className="pt-3 border-t border-slate-800 space-y-2">
              <span className="text-xs font-bold text-slate-400 block">Commit New Version to {selectedKey}:</span>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="New value"
                  value={newUpdateVal}
                  onChange={(e) => setNewUpdateVal(e.target.value)}
                  className="flex-1 bg-slate-950 text-xs font-mono text-slate-200 px-3 py-2 rounded-lg border border-slate-700"
                />
                <button
                  type="submit"
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-lg border border-slate-700 transition"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            </form>
          </div>

          {/* Version Chain Visualizer & Time-Travel Value Result */}
          <div className="lg:col-span-2 space-y-6">
            {/* Historical Value Comparison Banner */}
            {timeTravelResult && (
              <div className="bg-slate-900/90 border border-indigo-700/80 rounded-xl p-5 shadow-xl flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider block">
                    Snapshot Visible at Timestamp t={Number(timeTravelResult.as_of_timestamp).toFixed(2)}
                  </span>
                  <div className="mt-1 flex items-center gap-3">
                    <span className="text-2xl font-mono font-bold text-indigo-300">
                      {JSON.stringify(timeTravelResult.value)}
                    </span>
                    <span className="text-xs text-slate-500 font-mono">
                      (Current Head: {JSON.stringify(currentChain[currentChain.length - 1]?.value)})
                    </span>
                  </div>
                </div>

                <div className="text-right text-xs font-mono text-emerald-400 bg-emerald-950/60 px-3 py-1.5 rounded-lg border border-emerald-800">
                  Non-Blocking Snapshot
                </div>
              </div>
            )}

            {/* Version Chain Diagram */}
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg">
              <h3 className="text-sm font-bold text-slate-200 mb-4 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-cyan-400" />
                Version Chain for Key: <span className="text-cyan-300 font-mono font-bold">{selectedKey}</span>
              </h3>

              {currentChain.length === 0 ? (
                <div className="text-center py-12 text-slate-500 text-xs">
                  No versions recorded for key '{selectedKey}'
                </div>
              ) : (
                <div className="space-y-3">
                  {currentChain.map((ver, idx) => {
                    const isHead = idx === currentChain.length - 1;
                    const isQueriedVisible = timeTravelResult && (
                      ver.created_ts <= targetTimestamp &&
                      (ver.expired_ts === null || targetTimestamp < ver.expired_ts)
                    );

                    return (
                      <div
                        key={idx}
                        className={`p-3.5 rounded-xl border flex flex-wrap items-center justify-between gap-3 font-mono text-xs transition ${
                          isQueriedVisible
                            ? 'bg-indigo-950/80 border-indigo-500 text-indigo-100 shadow-lg shadow-indigo-900/30 ring-1 ring-indigo-500'
                            : 'bg-slate-950/70 border-slate-800 text-slate-300'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-[11px] text-slate-400">
                            v{idx + 1}
                          </span>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-100 text-sm">
                                Value: {JSON.stringify(ver.value)}
                              </span>
                              {isHead && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800">
                                  HEAD
                                </span>
                              )}
                              {isQueriedVisible && (
                                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-indigo-900 text-indigo-200 border border-indigo-700">
                                  ACTIVE SNAPSHOT
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-500">
                              Created by txn: <strong className="text-slate-300">{ver.txn_id}</strong>
                            </span>
                          </div>
                        </div>

                        <div className="text-right text-[11px] text-slate-400 space-y-0.5">
                          <div>
                            Created TS: <span className="text-slate-200 font-bold">{ver.created_ts.toFixed(2)}</span>
                          </div>
                          <div>
                            Expired TS: <span className="text-slate-200 font-bold">{ver.expired_ts ? ver.expired_ts.toFixed(2) : '∞ (Active)'}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
