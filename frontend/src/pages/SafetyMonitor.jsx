import {
  Activity, AlertOctagon, Flame, Gauge, Play, Radar, ShieldAlert, Timer,
  Volume2, VolumeX,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, SectionTitle } from '../components/ui.jsx';

// Browser speech-synthesis voice alerts for CAUTION / DANGER zones.
// Fires only on zone transitions decided by the deterministic backend rules.
function speakZone(zone) {
  try {
    const synth = window.speechSynthesis;
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(
      zone === 'DANGER'
        ? 'Danger. Danger. Object inside the critical zone. Stop the machine immediately.'
        : 'Caution. Object or person inside the proximity warning zone.');
    u.rate = 1.05;
    u.pitch = zone === 'DANGER' ? 0.8 : 1.0;
    u.volume = 1.0;
    synth.speak(u);
  } catch { /* speech synthesis optional */ }
}

export default function SafetyMonitor() {
  const { operator } = useAuth();
  const [live, setLive] = useState(null);
  const [flashAlert, setFlashAlert] = useState(null);
  const [toast, setToast] = useState('');
  const [voiceOn, setVoiceOn] = useState(true);
  const lastZoneRef = useRef(null);

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

  // Voice alerts on SAFE/CAUTION/DANGER zone transitions (deterministic
  // backend classification; speech synthesis is announcement-only).
  useEffect(() => {
    const zone = live?.active ? live.zone : null;
    if (!zone) { lastZoneRef.current = null; return; }
    if (zone !== lastZoneRef.current) {
      if (voiceOn && (zone === 'CAUTION' || zone === 'DANGER')) speakZone(zone);
      lastZoneRef.current = zone;
    }
  }, [live?.active, live?.zone, voiceOn]);

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
  const zone = live.zone || 'SAFE';

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
        <div className="flex items-center gap-2">
          <button
            className="btn-ghost text-xs inline-flex items-center gap-1"
            onClick={() => setVoiceOn((v) => !v)}
            title="Browser speech-synthesis voice alerts for CAUTION / DANGER zones"
          >
            {voiceOn ? <Volume2 size={14} /> : <VolumeX size={14} />}
            Voice alerts {voiceOn ? 'on' : 'off'}
          </button>
          <Badge tone="In Progress">ENGINE ON · {live.elapsed_min} min elapsed</Badge>
        </div>
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
          warn={zone === 'CAUTION'} danger={zone === 'DANGER'}
          sub={zone === 'SAFE' ? null
            : `${zone} zone${live.approaching ? ' — closing in!' : ''}`} />
      </div>

      <ProximityZonePanel live={live} />

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

const ZONE_STYLE = {
  SAFE: { dot: '#4ade80', text: 'text-green-300', border: 'border-green-500', bg: 'bg-green-600/15' },
  CAUTION: { dot: '#fbbf24', text: 'text-amber-300', border: 'border-amber-500', bg: 'bg-amber-600/15' },
  DANGER: { dot: '#f87171', text: 'text-red-300', border: 'border-red-500', bg: 'bg-red-600/15' },
};

// Visual proximity-zone indicator: concentric weather-adjusted hazard rings
// around the machine, with the detected object plotted at its (simulated)
// distance. All values come from the deterministic backend rule engine.
function ProximityZonePanel({ live }) {
  const zone = live.zone || 'SAFE';
  const style = ZONE_STYLE[zone];
  const warn = live.proximity_warn_m ?? 6;
  const crit = live.proximity_critical_m ?? 3;
  const dist = live.proximity_m ?? 0;
  const maxM = Math.max(warn * 1.7, dist * 1.15, 10); // metres to diagram edge
  const toPx = (m) => Math.min((m / maxM) * 140, 140);
  const ang = (-45 * Math.PI) / 180;
  const objR = toPx(dist);
  const objX = 160 + objR * Math.cos(ang);
  const objY = 160 + objR * Math.sin(ang);
  return (
    <div className={`panel border ${style.border}`}>
      <div className="flex items-start justify-between flex-wrap gap-2">
        <SectionTitle
          title="Dynamic Proximity Safety Zone"
          sub="Deterministic SAFE / CAUTION / DANGER classification — weather-adjusted radii plus time-to-contact of closing objects. Distance, closing speed and machine speed are simulated sensors."
        />
        <span className={`px-4 py-1.5 rounded-full border text-sm font-extrabold tracking-widest ${style.border} ${style.text} ${style.bg} ${zone !== 'SAFE' ? 'animate-pulse' : ''}`}>
          {zone}
        </span>
      </div>
      <div className="grid md:grid-cols-2 gap-6 items-center mt-2">
        <svg viewBox="0 0 320 320" className="w-full max-w-sm mx-auto">
          {/* SAFE area (outer) */}
          <circle cx="160" cy="160" r="140" fill="rgba(34,197,94,0.05)"
            stroke="#22c55e" strokeOpacity="0.35" strokeWidth="1.5" />
          {/* CAUTION ring = weather-adjusted warning radius */}
          <circle cx="160" cy="160" r={toPx(warn)} fill="rgba(245,158,11,0.08)"
            stroke="#f59e0b" strokeOpacity="0.8" strokeWidth="1.5" strokeDasharray="5 4" />
          {/* DANGER core = weather-adjusted critical radius */}
          <circle cx="160" cy="160" r={toPx(crit)} fill="rgba(239,68,68,0.15)"
            stroke="#ef4444" strokeOpacity="0.9" strokeWidth="2" />
          {/* machine at centre */}
          <rect x="146" y="146" width="28" height="28" rx="6" fill="#f7cf05" />
          <text x="160" y="164" textAnchor="middle" fontSize="11" fontWeight="800" fill="#111">CAT</text>
          {/* detected object/person at its simulated distance */}
          <circle cx={objX} cy={objY} r="14" fill={style.dot} opacity="0.25"
            className={live.approaching ? 'animate-pulse' : ''} />
          <circle cx={objX} cy={objY} r="6" fill={style.dot} stroke="#111" strokeWidth="1" />
          <text x={objX} y={objY - 20} textAnchor="middle" fontSize="10" fill="#d4d4d8">
            {dist.toFixed(1)} m
          </text>
          {/* ring labels */}
          <text x={160 + toPx(crit) * 0.74} y={160 - toPx(crit) * 0.74 - 4} fontSize="9" fill="#f87171">
            DANGER ≤ {crit} m
          </text>
          <text x={160 + toPx(warn) * 0.74} y={160 - toPx(warn) * 0.74 - 4} fontSize="9" fill="#fbbf24">
            CAUTION ≤ {warn} m
          </text>
          <text x="18" y="24" fontSize="9" fill="#4ade80">SAFE</text>
        </svg>
        <div className="space-y-2 text-sm">
          <Stat label="Distance to object" value={`${dist.toFixed(1)} m`} />
          <Stat label="Relative closing speed"
            value={live.closing_speed_mps != null
              ? `${live.closing_speed_mps.toFixed(2)} m/s` : '—'} />
          <Stat label="Time to contact"
            value={live.ttc_s != null ? `~${live.ttc_s} s` : '—'} />
          <Stat label="Machine ground speed"
            value={<>{(live.speed_kmh ?? 0).toFixed(1)} km/h{' '}
              <span className="text-[10px] text-zinc-500">SIMULATED</span></>} />
          <div className="text-xs text-zinc-400 pt-1">
            Weather-adjusted limits ({live.weather} ×{live.condition_factor}):
            CAUTION ≤ {warn} m · DANGER ≤ {crit} m
          </div>
          <div className={`text-xs ${style.text}`}>Why: {live.zone_reason}</div>
          <p className="text-[11px] text-zinc-500">
            Proximity distance, relative closing speed and machine ground speed
            are simulated telemetry for the demo. Zone classification is made by
            the deterministic safety rule engine — never by the AI assistant.
          </p>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="flex items-center justify-between border-b border-cat-line pb-1">
      <span className="text-zinc-400">{label}</span>
      <span className="font-bold text-zinc-100">{value}</span>
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
          <button className="btn-danger" onClick={() => simulate('vehicle_approaching')}>
            Vehicle Approaching Fast (live)
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
