import {
  Activity, AlertOctagon, Flame, Gauge, Play, Radar, ShieldAlert, Timer,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, SectionTitle } from '../components/ui.jsx';

export default function SafetyMonitor() {
  const { operator } = useAuth();
  const [live, setLive] = useState(null);
  const [flashAlert, setFlashAlert] = useState(null);
  const [toast, setToast] = useState('');

  // Poll live (simulated) telemetry every 2s; surface alerts immediately.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await api.get(`/safety/live/${operator.operator_id}`);
        if (cancelled) return;
        setLive(data.active ? data : { active: false });
        if (data.active && data.active_alert) raiseAlert(data.active_alert);
      } catch { /* ignore */ }
    };
    poll();
    const t = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(t); };
  }, [operator.operator_id]);

  const raiseAlert = (alert) => {
    setFlashAlert(alert);
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.frequency.value = 880; g.gain.value = 0.05;
      o.start(); setTimeout(() => { o.stop(); ctx.close(); }, 350);
    } catch { /* audio optional */ }
  };

  const simulate = async (eventType, weather) => {
    setToast('');
    try {
      const { data } = await api.post('/safety/simulate', {
        operator_id: operator.operator_id, event_type: eventType, weather,
      });
      if (data.alert) raiseAlert(data.alert);
      if (data.snapshot) setLive({ active: true, ...data.snapshot });
      if (data.pattern_injected) {
        setToast(`Behavior pattern "${data.pattern_injected}" injected into telemetry. `
          + 'Open Behavior Analysis to see detection.');
      }
    } catch (e) {
      setToast(e.response?.data?.detail || 'Simulation failed');
    }
  };

  if (!live) return <div className="text-zinc-400">Connecting to telemetry…</div>;

  if (!live.active) {
    return (
      <div className="panel max-w-xl">
        <SectionTitle title="Real-Time Safety Monitoring" />
        <p className="text-sm text-zinc-300">
          No active operation session. Start a task from the dashboard to begin
          live (simulated) sensor streaming.
        </p>
        <Link to="/" className="btn-primary mt-4 inline-flex">
          <Play size={16} /> Go to my tasks
        </Link>
        <p className="text-[11px] text-zinc-500 mt-3">
          Sensors are simulated for the hackathon demo; safety decisions come from
          deterministic rules, never from the AI assistant.
        </p>
      </div>
    );
  }

  const seatbeltBad = live.seatbelt === 'Unfastened';
  const proxCrit = live.proximity_critical_m ?? 3;
  const proxWarn = live.proximity_warn_m ?? 6;
  const proxBad = live.proximity_m <= proxCrit;
  const proxWarnState = !proxBad && live.proximity_m <= proxWarn;

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Real-Time Safety Monitoring</h1>
          <p className="text-sm text-zinc-400">
            Task {live.task_code} · {live.machine_id} · Weather: {live.weather} ·{' '}
            <span className="text-zinc-500">simulated telemetry (2 s refresh)</span>
          </p>
        </div>
        <Badge tone="In Progress">ENGINE ON · {live.elapsed_min} min elapsed</Badge>
      </div>

      {flashAlert && (
        <div className={`rounded-xl border-2 p-4 flex items-start gap-3 animate-pulse ${
          flashAlert.severity === 'CRITICAL'
            ? 'border-red-500 bg-red-600/20' : 'border-amber-500 bg-amber-600/20'}`}>
          <AlertOctagon className="text-red-400 shrink-0" size={26} />
          <div className="flex-1">
            <div className="font-extrabold text-red-300">
              {flashAlert.severity}: {flashAlert.incident_type}
            </div>
            <div className="text-sm">{flashAlert.description}</div>
            <div className="text-xs text-zinc-300 mt-1">
              Action: {flashAlert.action_taken} · Logged to incident log.
            </div>
          </div>
          <button className="btn-ghost text-xs" onClick={() => setFlashAlert(null)}>
            Dismiss
          </button>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <Tile icon={Gauge} label="Engine RPM" value={live.rpm} />
        <Tile icon={Flame} label="Fuel rate" value={`${live.fuel_rate_lph} L/h`} />
        <Tile icon={Activity} label="Load cycles" value={live.load_cycles} />
        <Tile icon={Timer} label="Idle time" value={`${live.idle_minutes} min`}
          warn={live.idle_minutes >= 1} />
        <Tile icon={ShieldAlert} label="Seatbelt" value={live.seatbelt} danger={seatbeltBad} />
        <Tile icon={Radar} label="Proximity" value={`${live.proximity_m} m`}
          warn={proxWarnState} danger={proxBad}
          sub={live.approaching ? 'Person approaching!' : null} />
      </div>

      <SimControls simulate={simulate} toast={toast} live={live} />
    </div>
  );
}

function Tile({ icon: Icon, label, value, warn, danger, sub }) {
  const border = danger ? 'border-red-500 bg-red-600/10'
    : warn ? 'border-amber-500 bg-amber-600/10' : 'border-cat-line';
  const text = danger ? 'text-red-400' : warn ? 'text-amber-300' : 'text-zinc-100';
  return (
    <div className={`panel border ${border}`}>
      <div className="flex items-center gap-2 text-xs uppercase text-zinc-400">
        <Icon size={14} /> {label}
      </div>
      <div className={`text-xl font-bold mt-1 ${text}`}>{value}</div>
      {sub && <div className="text-[11px] text-amber-300 mt-0.5 animate-pulse">{sub}</div>}
    </div>
  );
}

const WEATHERS = ['Sunny', 'Cloudy', 'Rainy', 'Windy', 'Fog', 'Night'];
const CONDITION_FACTOR = { Sunny: 1.0, Cloudy: 1.1, Rainy: 1.4, Windy: 1.25, Fog: 1.5, Night: 1.3 };

function SimControls({ simulate, toast, live }) {
  return (
    <>
      <div className="panel">
        <SectionTitle title="Environmental conditions"
          sub="Working conditions tighten the deterministic safety thresholds in real time — change the weather and watch the hazard zones grow." />
        <div className="flex flex-wrap items-center gap-2">
          {WEATHERS.map((w) => (
            <button
              key={w}
              onClick={() => simulate('weather_change', w)}
              className={live.weather === w ? 'btn-primary' : 'btn-ghost'}
            >
              {w} <span className="opacity-70 text-[11px]">×{CONDITION_FACTOR[w]}</span>
            </button>
          ))}
        </div>
        <div className="mt-3 text-sm text-zinc-300">
          Current: <span className="font-semibold text-cat-yellow">{live.weather}</span>
          {' '}→ proximity WARNING ≤ <span className="font-semibold text-amber-300">{live.proximity_warn_m} m</span>,
          CRITICAL ≤ <span className="font-semibold text-red-400">{live.proximity_critical_m} m</span>
          <span className="text-zinc-500"> (base 6.0 m / 3.0 m × {live.condition_factor})</span>
        </div>
        <p className="text-[11px] text-zinc-500 mt-2">
          Tip for the demo: start "Person Approaching" in Sunny weather, then switch to Fog
          while they are in the warning zone — the alert escalates to CRITICAL on its own.
        </p>
      </div>

      <div className="panel">
        <SectionTitle title="Safety event simulation"
          sub="Deterministic rule engine evaluates every event; CRITICAL events alert instantly and are logged." />
        <div className="flex flex-wrap gap-3">
          <button className="btn-danger" onClick={() => simulate('seatbelt_violation')}>
            Simulate Seatbelt Violation
          </button>
          <button className="btn-ghost" onClick={() => simulate('seatbelt_fixed')}>
            Fasten Seatbelt
          </button>
          <button className="btn-danger" onClick={() => simulate('person_approaching')}>
            Person Approaching (live)
          </button>
          <button className="btn-danger" onClick={() => simulate('proximity_hazard')}>
            Instant Proximity Hazard
          </button>
          <button className="btn-ghost" onClick={() => simulate('proximity_clear')}>
            Clear Hazard
          </button>
        </div>
      </div>

      <div className="panel">
        <SectionTitle title="Behavior pattern simulation"
          sub="Injects labelled telemetry patterns so the analyzer can detect and explain unusual behavior." />
        <div className="flex flex-wrap gap-3">
          <button className="btn-ghost" onClick={() => simulate('excessive_idling')}>
            Simulate Excessive Idling
          </button>
          <button className="btn-ghost" onClick={() => simulate('low_load')}>
            Simulate Low Load Activity
          </button>
          <button className="btn-ghost" onClick={() => simulate('fuel_anomaly')}>
            Simulate Unusual Fuel Usage
          </button>
          <Link to="/behavior" className="btn-primary">Open Behavior Analysis →</Link>
        </div>
        {toast && <div className="mt-3 text-sm text-cat-yellow">{toast}</div>}
      </div>
    </>
  );
}
