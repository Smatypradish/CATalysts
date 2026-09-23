import { GraduationCap, Microscope, RefreshCw } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, Empty, SectionTitle } from '../components/ui.jsx';

export default function BehaviorAnalysis() {
  const { operator } = useAuth();
  const [data, setData] = useState(null);
  const [telemetry, setTelemetry] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try {
      const [a, t] = await Promise.all([
        api.get(`/behavior/${operator.operator_id}/analyze`),
        api.get(`/behavior/${operator.operator_id}/telemetry`),
      ]);
      setData(a.data);
      setTelemetry(t.data);
    } catch {
      setError('Could not load behavior analysis. Is the backend running on :8001?');
    }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  const rerun = async () => { setBusy(true); await load(); setBusy(false); };

  if (error && !data) {
    return (
      <div className="panel max-w-xl">
        <p className="text-sm text-red-400">{error}</p>
        <button className="btn-primary mt-4" onClick={load}>Retry</button>
      </div>
    );
  }
  if (!data) return <div className="text-zinc-400">Analysing telemetry…</div>;

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">Unusual Behavior Detection</h1>
          <p className="text-sm text-zinc-400 max-w-3xl">{data.method}</p>
        </div>
        <button className="btn-ghost" onClick={rerun} disabled={busy}>
          <RefreshCw size={15} className={busy ? 'animate-spin' : ''} /> Re-run analysis
        </button>
      </div>

      {data.baseline && data.records > 0 && (
        <div className="panel grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
          <Baseline label="Records analysed" value={data.records}
            sub={`${data.baseline.dataset_records} supplied dataset`} />
          <Baseline label="Avg idling" value={`${data.baseline.avg_idling_min} min`} />
          <Baseline label="Avg load cycles" value={data.baseline.avg_load_cycles} />
          <Baseline label="Avg fuel/cycle" value={`${data.baseline.avg_fuel_per_cycle} L`} />
          <Baseline label="ML outliers"
            value={data.ml_outliers?.length ?? 0} sub="IsolationForest" />
        </div>
      )}

      <div>
        <SectionTitle title="Findings"
          sub="Every finding explains what was detected, why it is unusual, and the recommended action." />
        {data.findings.length === 0 && (
          <Empty text="No unusual behavior detected. Keep operating safely!" />
        )}
        <div className="space-y-3">
          {data.findings.map((f, i) => (
            <div key={i} className="panel">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="font-bold">{f.title}</div>
                <Badge>{f.severity}</Badge>
              </div>
              <div className="mt-2 grid md:grid-cols-3 gap-3 text-sm">
                <div>
                  <div className="text-[11px] uppercase text-zinc-500 font-semibold">What was detected</div>
                  <div className="mt-0.5">{f.detected}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase text-zinc-500 font-semibold">Why it is unusual</div>
                  <div className="mt-0.5 text-zinc-300">{f.why}</div>
                </div>
                <div>
                  <div className="text-[11px] uppercase text-zinc-500 font-semibold">Recommended action</div>
                  <div className="mt-0.5 text-zinc-300">{f.action}</div>
                  {f.recommended_module && (
                    <Link to="/training"
                      className="inline-flex items-center gap-1 text-xs text-cat-yellow mt-2 hover:underline">
                      <GraduationCap size={13} /> Linked module: {f.recommended_module}
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <TelemetryTable rows={telemetry} />
    </div>
  );
}

function Baseline({ label, value, sub }) {
  return (
    <div>
      <div className="text-[11px] uppercase text-zinc-500">{label}</div>
      <div className="text-lg font-bold">{value}</div>
      {sub && <div className="text-[11px] text-zinc-500">{sub}</div>}
    </div>
  );
}

function TelemetryTable({ rows }) {
  return (
    <div>
      <SectionTitle
        title="Telemetry records (supplied Dataset 1 + labelled simulated rows)"
        sub="Rows tagged 'dataset' are the exact records from the hackathon problem statement." />
      <div className="panel p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left uppercase text-zinc-400 border-b border-cat-line">
              {['Timestamp', 'Machine', 'Engine hrs', 'Fuel (L)', 'Load cycles',
                'Idle (min)', 'Seatbelt', 'Alert', 'Source'].map((h) => (
                <th key={h} className="px-3 py-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...rows].reverse().map((r, i) => (
              <tr key={i} className="border-b border-cat-line/40">
                <td className="px-3 py-2">{r.timestamp.replace('T', ' ').slice(0, 16)}</td>
                <td className="px-3 py-2">{r.machine_id}</td>
                <td className="px-3 py-2">{r.engine_hours}</td>
                <td className="px-3 py-2">{r.fuel_used}</td>
                <td className="px-3 py-2">{r.load_cycles}</td>
                <td className={`px-3 py-2 ${r.idling_time >= 45 ? 'text-amber-300 font-bold' : ''}`}>
                  {r.idling_time}
                </td>
                <td className={`px-3 py-2 ${r.seatbelt_status === 'Unfastened' ? 'text-red-400 font-bold' : ''}`}>
                  {r.seatbelt_status}
                </td>
                <td className={`px-3 py-2 ${r.safety_alert_triggered === 'Yes' ? 'text-red-400 font-bold' : ''}`}>
                  {r.safety_alert_triggered}
                </td>
                <td className="px-3 py-2"><Badge>{r.source}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
