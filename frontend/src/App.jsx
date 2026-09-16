import React, { useEffect, useRef, useState } from 'react';
import { 
  LayoutDashboard, 
  GitCommit, 
  ShieldCheck, 
  Network, 
  History, 
  AlertOctagon, 
  BarChart3, 
  RefreshCw,
  X,
  Database,
  Terminal,
  Radio
} from 'lucide-react';

import LiveControlRoom from './components/LiveControlRoom';
import WaitForGraph from './components/WaitForGraph';
import IsolationPlayground from './components/IsolationPlayground';
import SerializabilityChecker from './components/SerializabilityChecker';
import MVCCTimeTravel from './components/MVCCTimeTravel';
import ChaosRecovery from './components/ChaosRecovery';
import BenchmarkDashboard from './components/BenchmarkDashboard';

export default function App() {
  const [activeTab, setActiveTab] = useState('control_room');
  const [connected, setConnected] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [state, setState] = useState({
    protocol: '2PL',
    deadlock_mode: 'detection',
    prevention_scheme: 'wound_wait',
    victim_policy: 'youngest',
    storage: {},
    wait_for_graph: {},
    locks: [],
    transactions: [],
    wal_records: [],
    deadlock_history: [],
  });
  const [isRefreshing, setIsRefreshing] = useState(false);

  const wsRef = useRef(null);

  const addNotification = (message, type = 'info') => {
    const id = Date.now() + Math.random();
    const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false });
    setNotifications((prev) => [...prev.slice(-3), { id, message, type, timeStr }]);
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.id !== id));
    }, 4500);
  };

  const fetchState = async () => {
    setIsRefreshing(true);
    try {
      const res = await fetch('/api/state');
      if (res.ok) {
        const data = await res.json();
        setState(data);
      }
    } catch (err) {
      console.error('Failed to fetch system state:', err);
    } finally {
      setTimeout(() => setIsRefreshing(false), 300);
    }
  };

  // Setup WebSocket connection for live event streaming
  useEffect(() => {
    fetchState();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;

    let reconnectTimer;

    const connect = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        addNotification('Connected to engine telemetry stream', 'info');
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'full_state') {
            setState(msg.data);
          } else if (msg.type === 'txn_submitted' || msg.type === 'txn_status' || msg.type === 'txn_op') {
            fetchState();
          } else if (msg.type === 'protocol_changed') {
            fetchState();
            addNotification(`Active protocol updated: ${msg.data.protocol}`, 'info');
          } else if (msg.type === 'deadlock_mode_changed') {
            fetchState();
          } else if (msg.type === 'system_crashed') {
            fetchState();
            addNotification('SYSTEM CRASH: Volatile memory wiped. Disk WAL preserved.', 'error');
          } else if (msg.type === 'recovery_completed') {
            fetchState();
            addNotification('ARIES-Lite 3-Pass Recovery complete', 'success');
          } else {
            fetchState();
          }
        } catch (e) {
          console.error(e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      if (wsRef.current) wsRef.current.close();
      clearTimeout(reconnectTimer);
    };
  }, []);

  const tabs = [
    { id: 'control_room', num: '01', name: 'Control Console', subtitle: 'Live execution & storage', icon: LayoutDashboard },
    { id: 'wait_for_graph', num: '02', name: 'Wait-For Graph', subtitle: 'Lock cycles & victims', icon: GitCommit },
    { id: 'isolation_lab', num: '03', name: 'Isolation Lab', subtitle: 'Anomaly matrix & proofs', icon: ShieldCheck },
    { id: 'serializability', num: '04', name: 'Serializability', subtitle: 'Precedence graph checker', icon: Network },
    { id: 'mvcc_travel', num: '05', name: 'MVCC Time-Travel', subtitle: 'Version chains & as-of', icon: History },
    { id: 'chaos_recovery', num: '06', name: 'Chaos & Recovery', subtitle: 'Crash & ARIES 3-pass', icon: AlertOctagon },
    { id: 'benchmarks', num: '07', name: 'Benchmarks', subtitle: 'Throughput & abort trade-offs', icon: BarChart3 },
  ];

  const activeWorkerCount = (state.transactions || []).filter(
    (t) => t.status === 'RUNNING' || t.status === 'WAITING'
  ).length;

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-200 flex flex-col font-sans selection:bg-blue-600/30 selection:text-white">
      {/* Top Academic Masthead & System Instrumentation Bar */}
      <header className="sticky top-0 z-40 bg-[#0c121e]/95 backdrop-blur-md border-b border-slate-800/80 px-6 py-3">
        <div className="max-w-[1440px] mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Masthead */}
          <div className="flex items-center gap-3.5">
            <div className="w-8 h-8 rounded bg-slate-900 border border-slate-700/80 flex items-center justify-center text-blue-400 font-mono text-sm font-bold shadow-sm">
              <Database className="w-4 h-4 text-blue-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-semibold tracking-tight text-white uppercase">
                  DBMS Transaction Manager Simulator
                </h1>
                <span className="font-mono text-[10px] text-slate-400 px-1.5 py-0.5 rounded bg-slate-800/70 border border-slate-700/60 uppercase">
                  v1.0 &bull; Academic Edition
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono tracking-normal">
                First-Principles Engine &bull; Thread-Safe KV Store &bull; On-Disk WAL &bull; Real Threads
              </p>
            </div>
          </div>

          {/* Right Status Instrumentation Strip */}
          <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono">
            {/* Protocol Indicator */}
            <div className="bg-[#111827] px-2.5 py-1 rounded border border-slate-800 flex items-center gap-1.5 text-slate-300">
              <span className="text-[10px] text-slate-400 uppercase">Protocol:</span>
              <span className="font-bold text-blue-400">{state.protocol}</span>
            </div>

            {/* In-Flight Active Workers */}
            <div className="bg-[#111827] px-2.5 py-1 rounded border border-slate-800 flex items-center gap-1.5 text-slate-300">
              <span className="text-[10px] text-slate-400 uppercase">Threads:</span>
              <span className={activeWorkerCount > 0 ? 'font-bold text-amber-400' : 'text-slate-400'}>
                {activeWorkerCount} active
              </span>
            </div>

            {/* WebSocket Telemetry Status */}
            <div className={`px-2.5 py-1 rounded border flex items-center gap-1.5 ${
              connected 
                ? 'bg-emerald-950/40 border-emerald-800/70 text-emerald-300' 
                : 'bg-amber-950/40 border-amber-800/70 text-amber-300'
            }`}>
              <Radio className={`w-3 h-3 ${connected ? 'text-emerald-400 animate-pulse' : 'text-amber-400'}`} />
              <span className="text-[11px] font-medium tracking-wide">
                {connected ? 'LIVE TELEMETRY' : 'CONNECTING...'}
              </span>
            </div>

            {/* Refresh State Trigger */}
            <button
              onClick={fetchState}
              disabled={isRefreshing}
              className="p-1.5 rounded bg-[#111827] hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-800 transition disabled:opacity-50"
              title="Synchronize state from backend"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Technical Tab Navigation Bar */}
        <div className="max-w-[1440px] mx-auto mt-3 pt-2.5 border-t border-slate-800/60 flex items-center gap-1 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`group flex items-center gap-2.5 px-3.5 py-1.5 rounded text-xs transition relative whitespace-nowrap ${
                  isActive
                    ? 'bg-slate-800/90 text-white font-medium border border-slate-700/80 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60 border border-transparent'
                }`}
              >
                <span className={`font-mono text-[10px] ${isActive ? 'text-blue-400' : 'text-slate-400'}`}>
                  {tab.num}
                </span>
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-blue-400' : 'text-slate-400 group-hover:text-slate-300'}`} />
                <span>{tab.name}</span>
                {isActive && (
                  <span className="absolute bottom-0 left-2 right-2 h-[2px] bg-blue-500 rounded-full"></span>
                )}
              </button>
            );
          })}
        </div>
      </header>

      {/* Main Content Workspace */}
      <main className="flex-1 max-w-[1440px] w-full mx-auto p-5 md:p-6">
        {activeTab === 'control_room' && (
          <LiveControlRoom state={state} onRefresh={fetchState} onNotify={addNotification} />
        )}
        {activeTab === 'wait_for_graph' && (
          <WaitForGraph state={state} onRefresh={fetchState} onNotify={addNotification} />
        )}
        {activeTab === 'isolation_lab' && (
          <IsolationPlayground onNotify={addNotification} />
        )}
        {activeTab === 'serializability' && (
          <SerializabilityChecker onNotify={addNotification} />
        )}
        {activeTab === 'mvcc_travel' && (
          <MVCCTimeTravel state={state} onRefresh={fetchState} onNotify={addNotification} />
        )}
        {activeTab === 'chaos_recovery' && (
          <ChaosRecovery state={state} onRefresh={fetchState} onNotify={addNotification} />
        )}
        {activeTab === 'benchmarks' && (
          <BenchmarkDashboard onNotify={addNotification} />
        )}
      </main>

      {/* Structured Technical Toast Stream */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2 max-w-sm pointer-events-none">
        {notifications.map((n) => {
          const typeBorder = {
            success: 'border-emerald-800/80 bg-[#0a1813]/95 text-emerald-200',
            warning: 'border-amber-800/80 bg-[#19140a]/95 text-amber-200',
            error: 'border-rose-800/80 bg-[#1c0d10]/95 text-rose-200',
            info: 'border-slate-700 bg-[#0d131f]/95 text-slate-200',
          }[n.type] || 'border-slate-700 bg-[#0d131f]/95 text-slate-200';

          return (
            <div
              key={n.id}
              className={`pointer-events-auto p-3 rounded border text-xs font-mono shadow-xl backdrop-blur-sm flex items-start justify-between gap-3 ${typeBorder}`}
            >
              <div className="flex-1">
                <span className="text-[10px] text-slate-400 block mb-0.5">[{n.timeStr}] SYSTEM_EVENT</span>
                <p className="text-xs leading-relaxed font-sans">{n.message}</p>
              </div>
              <button
                onClick={() => setNotifications((prev) => prev.filter((item) => item.id !== n.id))}
                className="text-slate-400 hover:text-white p-0.5 transition"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Engineering Footer */}
      <footer className="border-t border-slate-800/70 bg-[#070a10] px-6 py-3 text-xs text-slate-400 font-mono flex flex-wrap items-center justify-between gap-3">
        <div>
          <span>INVARIANT: </span>
          <span className="text-slate-400">WAL append &amp; fsync() strictly precedes storage_engine.put()</span>
        </div>
        <div className="flex items-center gap-4 text-[11px]">
          <span>CONCURRENCY: Native OS Threads</span>
          <span>RECOVERY: ARIES-Lite (Analysis &bull; Redo &bull; Undo)</span>
        </div>
      </footer>
    </div>
  );
}
