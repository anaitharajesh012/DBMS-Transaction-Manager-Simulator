import React, { useState } from 'react';
import { 
  BarChart3, 
  Play, 
  TrendingUp, 
  Layers, 
  ShieldAlert, 
  Activity, 
  HelpCircle 
} from 'lucide-react';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer 
} from 'recharts';

export default function BenchmarkDashboard({ onNotify }) {
  const [numTxns, setNumTxns] = useState(40);
  const [contention, setContention] = useState('high');
  const [writeRatio, setWriteRatio] = useState(0.5);
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRunBenchmark = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/benchmark', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          num_txns: Number(numTxns),
          contention,
          write_ratio: Number(writeRatio),
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setBenchmarkData(data);
        onNotify('Benchmark suite completed successfully across all protocols!', 'success');
      }
    } catch (err) {
      onNotify('Benchmark run failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const protocolsData = benchmarkData?.protocols || [];
  const deadlockData = benchmarkData?.deadlock_comparison || [];

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="w-5 h-5 text-indigo-400" />
          <h2 className="text-lg font-bold text-slate-100">Cross-Protocol & Concurrency Control Benchmark</h2>
        </div>
        <p className="text-xs text-slate-400 leading-relaxed">
          Quantifies empirical trade-offs between concurrency strategies under identical synthetic workloads. Compares Throughput (TPS), Latency (ms), and Abort Rates (%) across Strict 2PL, Timestamp Ordering, OCC, and MVCC, alongside Deadlock Detection vs Prevention schemes.
        </p>
      </div>

      {/* Benchmark Workload Configuration */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-center gap-5 text-xs">
          <div>
            <label className="block text-slate-400 font-bold uppercase mb-1.5">Transactions / Protocol</label>
            <select
              value={numTxns}
              onChange={(e) => setNumTxns(e.target.value)}
              className="bg-slate-950 font-mono text-slate-200 rounded-lg px-3 py-2 border border-slate-700 font-bold"
            >
              <option value={20}>20 Transactions</option>
              <option value={40}>40 Transactions</option>
              <option value={80}>80 Transactions</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 font-bold uppercase mb-1.5">Contention Level</label>
            <select
              value={contention}
              onChange={(e) => setContention(e.target.value)}
              className="bg-slate-950 text-slate-200 rounded-lg px-3 py-2 border border-slate-700 font-bold"
            >
              <option value="high">High Contention (2 Hot Keys)</option>
              <option value="medium">Medium Contention (5 Keys)</option>
              <option value="low">Low Contention (20 Keys)</option>
            </select>
          </div>

          <div>
            <label className="block text-slate-400 font-bold uppercase mb-1.5">Write Ratio: {Math.round(writeRatio * 100)}%</label>
            <input
              type="range"
              min="0.1"
              max="0.9"
              step="0.1"
              value={writeRatio}
              onChange={(e) => setWriteRatio(e.target.value)}
              className="accent-indigo-500 cursor-pointer w-32"
            />
          </div>
        </div>

        <button
          onClick={handleRunBenchmark}
          disabled={loading}
          className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
        >
          <Play className="w-4 h-4" />
          {loading ? 'Benchmarking...' : 'Run Benchmark Suite'}
        </button>
      </div>

      {/* Benchmark Results */}
      {benchmarkData ? (
        <div className="space-y-6">
          {/* Section 1: 4 Protocols Comparison */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                Protocol Comparison (Strict 2PL vs TO vs OCC vs MVCC)
              </h3>
              <span className="text-xs font-mono text-slate-400">
                Contention: {contention.toUpperCase()} | Write Ratio: {Math.round(writeRatio * 100)}%
              </span>
            </div>

            {/* Recharts Bar Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Throughput Chart */}
              <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
                <span className="text-xs font-bold text-slate-300 block mb-3">Throughput (Txns / Sec) — Higher is Better</span>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={protocolsData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="protocol" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                      <Bar dataKey="throughput_tps" fill="#6366f1" radius={[4, 4, 0, 0]} name="Throughput (TPS)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Latency Chart */}
              <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
                <span className="text-xs font-bold text-slate-300 block mb-3">Average Latency (ms) — Lower is Better</span>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={protocolsData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="protocol" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                      <Bar dataKey="avg_latency_ms" fill="#06b6d4" radius={[4, 4, 0, 0]} name="Latency (ms)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Abort Rate Chart */}
              <div className="bg-slate-950/70 p-4 rounded-xl border border-slate-800">
                <span className="text-xs font-bold text-slate-300 block mb-3">Conflict Abort Rate (%) — Lower is Better</span>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={protocolsData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="protocol" stroke="#94a3b8" fontSize={11} />
                      <YAxis stroke="#94a3b8" fontSize={11} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: '12px' }} />
                      <Bar dataKey="abort_rate_pct" fill="#f43f5e" radius={[4, 4, 0, 0]} name="Abort Rate (%)" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Protocol Metrics Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950 text-slate-400 uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Protocol</th>
                    <th className="py-2.5 px-3">Total Txns</th>
                    <th className="py-2.5 px-3">Committed</th>
                    <th className="py-2.5 px-3">Aborted</th>
                    <th className="py-2.5 px-3">Throughput (TPS)</th>
                    <th className="py-2.5 px-3">Avg Latency</th>
                    <th className="py-2.5 px-3">Abort Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {protocolsData.map((p) => (
                    <tr key={p.protocol} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-bold text-indigo-300">{p.protocol}</td>
                      <td className="py-2.5 px-3 text-slate-300">{p.total_txns}</td>
                      <td className="py-2.5 px-3 text-emerald-400 font-bold">{p.committed}</td>
                      <td className="py-2.5 px-3 text-rose-400 font-bold">{p.aborted}</td>
                      <td className="py-2.5 px-3 text-cyan-300 font-bold">{p.throughput_tps}</td>
                      <td className="py-2.5 px-3 text-slate-200">{p.avg_latency_ms} ms</td>
                      <td className="py-2.5 px-3 text-amber-300">{p.abort_rate_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Section 2: Deadlock Detection vs Prevention Comparison */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-lg space-y-5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                Deadlock Strategy Analysis (Detection vs Prevention Schemes)
              </h3>
              <span className="text-xs text-slate-400 font-mono">Under High Write Contention</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-950 text-slate-400 uppercase border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Deadlock Scheme</th>
                    <th className="py-2.5 px-3">Mechanism</th>
                    <th className="py-2.5 px-3">Committed</th>
                    <th className="py-2.5 px-3">Aborted</th>
                    <th className="py-2.5 px-3">Throughput (TPS)</th>
                    <th className="py-2.5 px-3">Abort Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {deadlockData.map((d, i) => (
                    <tr key={i} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-bold text-amber-300">{d.strategy_label}</td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {d.strategy_label.includes('Wound-Wait') ? 'Preemptive: Older wounds younger' :
                         d.strategy_label.includes('Wait-Die') ? 'Non-Preemptive: Younger dies immediately' :
                         'Background DFS cycle detection'}
                      </td>
                      <td className="py-2.5 px-3 text-emerald-400 font-bold">{d.committed}</td>
                      <td className="py-2.5 px-3 text-rose-400 font-bold">{d.aborted}</td>
                      <td className="py-2.5 px-3 text-cyan-300 font-bold">{d.throughput_tps}</td>
                      <td className="py-2.5 px-3 text-slate-200">{d.abort_rate_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Academic Discussion Callout */}
            <div className="bg-slate-950/80 p-4 rounded-lg border border-slate-800 text-xs text-slate-300 space-y-2 leading-relaxed">
              <span className="text-indigo-300 font-bold block">Key Architectural Insights:</span>
              <ul className="list-disc pl-5 space-y-1 text-slate-400">
                <li>
                  <strong className="text-slate-200">Strict 2PL</strong> minimizes wasted work but suffers from blocking wait queues and deadlock vulnerabilities under hot-spot contention.
                </li>
                <li>
                  <strong className="text-slate-200">OCC (Kung-Robinson)</strong> achieves near-zero latency when write conflict is low, but incurs cascading aborts when multiple transactions validate against shared write-sets concurrently.
                </li>
                <li>
                  <strong className="text-slate-200">MVCC</strong> provides the highest throughput for mixed read/write workloads because readers never acquire locks and read historical snapshot versions.
                </li>
                <li>
                  <strong className="text-slate-200">Wound-Wait vs Wait-Die</strong>: Wound-Wait minimizes preemptive aborts because older transactions only wound younger holders if contention occurs, whereas Wait-Die aggressively kills younger requestors on any lock conflict.
                </li>
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-12 text-center text-slate-500 text-sm">
          Click "Run Benchmark Suite" above to execute multi-threaded workloads across all 4 protocols and generate quantitative charts!
        </div>
      )}
    </div>
  );
}
