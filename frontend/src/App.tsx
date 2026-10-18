import { useEffect, useMemo, useState } from 'react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type Sample = { id: number; observed_at: string; service_name: string; metric_name: string; metric_value: number; unit?: string; attributes?: Record<string, unknown> };
type Alert = { id: number; created_at: string; service_name: string; metric_name: string; severity: string; message: string; observed_value: number; resolved: boolean };
const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function App() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState<'loading'|'online'|'offline'>('loading');
  const [updated, setUpdated] = useState('—');
  async function refresh() {
    try {
      const [m, a] = await Promise.all([fetch(`${API}/metrics?since_minutes=60&limit=1000`), fetch(`${API}/alerts?limit=30`)]);
      if (!m.ok || !a.ok) throw new Error('API unavailable');
      setSamples(await m.json()); setAlerts(await a.json()); setStatus('online'); setUpdated(new Date().toLocaleTimeString());
    } catch { setStatus('offline'); }
  }
  useEffect(() => { void refresh(); const id = window.setInterval(() => void refresh(), 15000); return () => window.clearInterval(id); }, []);
  const latency = useMemo(() => samples.filter(s => /latency|duration/i.test(s.metric_name)), [samples]);
  const chartData = useMemo(() => {
    const byTime = new Map<string, { time: string; value: number }>();
    latency.slice().reverse().forEach(s => { const d = new Date(s.observed_at); const key = d.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'}); byTime.set(`${key}-${s.metric_name}`, {time:key, value:s.metric_value}); });
    return Array.from(byTime.values()).slice(-100);
  }, [latency]);
  const services = new Set(samples.map(s => s.service_name)).size;
  const active = alerts.filter(a => !a.resolved).length;
  const latestLatency = latency.length ? latency[0].metric_value : null;
  return <div className="shell">
    <aside className="sidebar"><div className="brand"><div className="brand-mark">O</div><div><b>observa<span>dash</span></b><small>METRICS INTELLIGENCE</small></div></div><div className="nav-label">WORKSPACE</div><div className="nav-item selected">◈ <span>Overview</span></div><div className="nav-item">⌁ <span>Service metrics</span></div><div className="nav-item">⚑ <span>Alert history</span><i>{active}</i></div><div className="nav-label lower">PLATFORM</div><div className="nav-item">◎ <span>Service map</span></div><div className="nav-item">⚙ <span>Settings</span></div><div className="side-bottom"><div className="avatar">OD</div><div><b>Observability team</b><small>Demo workspace</small></div><span className="dots">•••</span></div></aside>
    <main className="main"><header><div><div className="eyebrow">OBSERVABILITY / OVERVIEW</div><h1>Application health</h1><p className="subtitle">Monitor performance, detect anomalies, and understand service behavior.</p></div><div className="head-actions"><span className={`status ${status}`}><i/> {status==='online'?'API connected':status==='offline'?'API unavailable':'Connecting'}</span><button onClick={() => void refresh()}>↻ Refresh</button></div></header>
      <div className="range-row"><div className="tabs"><button className="active">Last hour</button><button onClick={() => void refresh()}>Live view</button><button>Custom range</button></div><span className="updated">Updated {updated}</span></div>
      <section className="stats"><Stat label="Monitored services" value={String(services)} sub="Seen in last 60 minutes" icon="◈"/><Stat label="Active alerts" value={String(active)} sub={active ? 'Requires attention' : 'No active alerts'} icon="⚑" alert={active>0}/><Stat label="Latest latency sample" value={latestLatency===null?'—':`${latestLatency.toFixed(1)} ms`} sub="From available metric samples" icon="◷"/><Stat label="Metric samples" value={samples.length.toLocaleString()} sub="Last 60 minutes" icon="⌁"/></section>
      <section className="panel chart-panel"><div className="panel-head"><div><h2>Latency overview</h2><p>Samples reported by instrumented services</p></div><div className="legend"><span/>Latency samples</div></div>{chartData.length ? <div className="chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData}><defs><linearGradient id="latencyFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7c8cff" stopOpacity={0.32}/><stop offset="100%" stopColor="#7c8cff" stopOpacity={0.01}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" stroke="#202a3c" vertical={false}/><XAxis dataKey="time" tick={{fill:'#71809a',fontSize:11}} axisLine={false} tickLine={false}/><YAxis tick={{fill:'#71809a',fontSize:11}} axisLine={false} tickLine={false} width={42}/><Tooltip contentStyle={{background:'#111a2b',border:'1px solid #2a3650',borderRadius:10,color:'#e7ecf7'}}/><Area type="monotone" dataKey="value" name="Latency" stroke="#8794ff" strokeWidth={2} fill="url(#latencyFill)" connectNulls/></AreaChart></ResponsiveContainer></div> : <Empty title="Waiting for latency metrics" body="Send metrics named with 'latency' or 'duration' to populate this chart."/>}</section>
      <section className="bottom-grid"><div className="panel"><div className="panel-head"><div><h2>Recent alerts</h2><p>Threshold and anomaly events</p></div><span className="pill">{alerts.length} events</span></div>{alerts.length ? <div className="alert-list">{alerts.slice(0,6).map(a=><div className="alert-row" key={a.id}><div className="alert-symbol">!</div><div className="alert-copy"><b>{a.message}</b><small>{a.service_name} · {new Date(a.created_at).toLocaleString()}</small></div><span className={`severity ${a.severity}`}>{a.severity}</span></div>)}</div>:<Empty title="No alerts recorded" body="Alert events will appear here when a configured threshold is exceeded."/>}</div>
      <div className="panel"><div className="panel-head"><div><h2>Service inventory</h2><p>Services seen in the last hour</p></div><span className="pill">{services} services</span></div>{services ? <div className="service-list">{Array.from(new Set(samples.map(s=>s.service_name))).map(name=><div className="service-row" key={name}><span className="service-dot"/><div><b>{name}</b><small>{samples.filter(s=>s.service_name===name).length} samples</small></div><span className="healthy">Observed</span></div>)}</div>:<Empty title="No services discovered" body="Start the collector or post a metric batch to the API."/>}</div></section>
      <footer><span>ObservaDash <b>v1.0</b></span><span>Metrics refresh every 15 seconds · Last refresh {updated}</span></footer>
    </main>
  </div>;
}
function Stat({label,value,sub,icon,alert=false}:{label:string;value:string;sub:string;icon:string;alert?:boolean}) { return <div className="stat-card"><div className="stat-top"><span>{label}</span><span className={`stat-icon ${alert?'warn':''}`}>{icon}</span></div><strong>{value}</strong><small>{sub}</small></div> }
function Empty({title,body}:{title:string;body:string}) { return <div className="empty"><div className="empty-icon">⌁</div><b>{title}</b><p>{body}</p></div> }
