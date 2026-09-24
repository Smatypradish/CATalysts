import { AlertTriangle, CheckCircle2, TrendingDown, TrendingUp } from 'lucide-react';
import { useEffect, useState } from 'react';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, SectionTitle } from '../components/ui.jsx';

export default function History() {
  const { operator } = useAuth();
  const [history, setHistory] = useState(null);
  const [error, setError] = useState('');

  const load = () => {
    setError('');
    api.get(`/history/${operator.operator_id}/performance`)
      .then(({ data }) => setHistory(data))
      .catch(() => setError('Could not load operation history. Is the backend running on :8001?'));
  };

  useEffect(() => { load(); }, [operator.operator_id]); // eslint-disable-line

  if (error) {
    return (
      <div className="panel max-w-xl">
        <p className="text-sm text-red-400">{error}</p>
        <button className="btn-primary mt-4" onClick={load}>Retry</button>
      </div>
    );
  }
  if (!history) return <div className="text-zinc-400">Loading history…</div>;

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-extrabold">Operation History</h1>
        <p className="text-sm text-zinc-400">
          Completed tasks, prediction accuracy, safety incidents, and data provenance.
        </p>
      </div>

      <div>
        <SectionTitle title="Completed tasks — predicted vs actual"
          sub="Actual times in this demo are simulated on task completion; predictions come from the trained model." />
        <div className="panel p-0 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-zinc-400 border-b border-cat-line">
                {['Task', 'Type', 'Weather', 'Estimated', 'Predicted', 'Actual', 'Variance', 'Completed'].map((h) => (
                  <th key={h} className="px-4 py-2">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {history.completed_tasks.length === 0 && (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-zinc-500">
                  No completed tasks yet. Finish a task to see prediction accuracy here.
                </td></tr>
              )}
              {history.completed_tasks.map((t) => {
                const v = t.variance_min;
                return (
                  <tr key={t.task_code} className="border-b border-cat-line/40">
                    <td className="px-4 py-2 font-semibold">{t.task_code}</td>
                    <td className="px-4 py-2">{t.task_type}</td>
                    <td className="px-4 py-2">{t.weather}</td>
                    <td className="px-4 py-2">{t.estimated_time} min</td>
                    <td className="px-4 py-2 text-cat-yellow font-semibold">
                      {t.predicted_time != null ? `${t.predicted_time} min` : '—'}
                    </td>
                    <td className="px-4 py-2">{t.actual_time} min</td>
                    <td className="px-4 py-2">
                      {v != null && (
                        <span className={`inline-flex items-center gap-1 font-semibold ${v > 0 ? 'text-amber-300' : 'text-emerald-300'}`}>
                          {v > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                          {v > 0 ? '+' : ''}{v} min
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-zinc-400">
                      {t.completed_at ? t.completed_at.replace('T', ' ').slice(0, 16) : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <SummaryCards history={history} />
      <RecordsTable rows={history.historical_records} />
    </div>
  );
}

function SummaryCards({ history }) {
  const nDataset = history.historical_records.filter((r) => r.source === 'dataset').length;
  const nSynth = history.historical_records.filter((r) => r.source === 'synthetic').length;
  return (
    <div className="grid md:grid-cols-2 gap-4">
      <div className="panel">
        <SectionTitle title="Safety incidents by severity"
          sub={`${history.incident_count} total · ${history.open_findings} open behavior finding(s)`} />
        <div className="space-y-2">
          {Object.entries(history.incidents_by_severity).map(([sev, n]) => (
            <div key={sev} className="flex items-center justify-between text-sm">
              <span className="inline-flex items-center gap-2">
                {sev === 'CRITICAL'
                  ? <AlertTriangle size={14} className="text-red-400" />
                  : <CheckCircle2 size={14} className="text-zinc-500" />}
                <Badge>{sev}</Badge>
              </span>
              <span className="font-bold">{n}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="panel">
        <SectionTitle title="Records provenance"
          sub="Which training records came from the supplied Caterpillar dataset vs labelled synthetic generation." />
        <div className="text-sm space-y-2">
          <div className="flex justify-between">
            <span className="text-zinc-400">Original Caterpillar records (Dataset 2)</span>
            <b>{nDataset}</b>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-400">Synthetic prototype records</span>
            <b>{nSynth}</b>
          </div>
          <div className="flex justify-between border-t border-cat-line/40 pt-2">
            <span className="text-zinc-300 font-medium">Total training records</span>
            <b>{nDataset + nSynth}</b>
          </div>
          <p className="text-[11px] text-zinc-500 pt-2">
            Original rows are loaded verbatim from data/task_records.csv and embedded
            unchanged in data/task_records_100.csv; synthetic rows come from a documented,
            deterministic formula (backend/generate_task_records_100.py). Every record
            carries a source tag.
          </p>
        </div>
      </div>
    </div>
  );
}

function RecordsTable({ rows }) {
  return (
    <div>
      <SectionTitle title="Historical task records"
        sub="Every record used by the ML model, with its source label." />
      <div className="panel p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left uppercase text-zinc-400 border-b border-cat-line">
              {['Task ID', 'Type', 'Weather', 'Skill', 'Machine age', 'Estimated', 'Actual', 'Source'].map((h) => (
                <th key={h} className="px-3 py-2">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.task_id} className="border-b border-cat-line/40">
                <td className="px-3 py-2 font-semibold">{r.task_id}</td>
                <td className="px-3 py-2">{r.task_type}</td>
                <td className="px-3 py-2">{r.weather}</td>
                <td className="px-3 py-2">{r.operator_skill}</td>
                <td className="px-3 py-2">{r.machine_age} yrs</td>
                <td className="px-3 py-2">{r.estimated_time}</td>
                <td className="px-3 py-2">{r.actual_time}</td>
                <td className="px-3 py-2"><Badge>{r.source}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
