import {
  BrainCircuit, ChevronRight, GraduationCap,
  Gauge, ShieldAlert, ShieldCheck, Sparkles, Wrench,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, SectionTitle, StatCard } from '../components/ui.jsx';

export default function Dashboard() {
  const { operator } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  const load = () =>
    api.get(`/dashboard/${operator.operator_id}`)
      .then(({ data }) => setData(data))
      .catch(() => setError('Cannot reach backend. Is it running on :8001?'));

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line

  if (error) return <div className="panel text-red-400">{error}</div>;
  if (!data) return <div className="text-zinc-400">Loading dashboard…</div>;

  const safetyTone = data.safety.status === 'SAFE' ? 'safe'
    : data.safety.status === 'WARNING' ? 'warn' : 'danger';

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">
            Good shift, <span className="text-cat-yellow">{data.operator.name}</span>
          </h1>
          <p className="text-sm text-zinc-400">
            {data.date} · {data.operator.operator_id} · Skill: {data.operator.skill} ·{' '}
            {data.operator.certifications}
          </p>
        </div>
        {data.live_session && (
          <Badge tone="In Progress">LIVE OPERATION (simulated telemetry)</Badge>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Wrench} label="Machine"
          value={data.machine ? `${data.machine.machine_id} · ${data.machine.model}` : '—'}
          sub={data.machine ? `${data.machine.machine_type}, age ${data.machine.age_years} yrs, ${data.machine.engine_hours} eng. hrs` : ''} />
        <StatCard icon={Gauge} label="Machine status"
          value={data.machine?.status ?? '—'}
          sub={data.active_task ? `On task ${data.active_task}` : 'No active task'}
          tone={data.machine?.status === 'Available' ? 'safe' : 'warn'} />
        <StatCard icon={data.safety.status === 'SAFE' ? ShieldCheck : ShieldAlert}
          label="Safety status" value={data.safety.status}
          sub={`${data.safety.open_incidents} open incident(s)`} tone={safetyTone} />
        <StatCard icon={BrainCircuit} label="Behavior findings"
          value={`${data.behavior_counts.findings}`}
          sub={`${data.behavior_counts.critical_high} high/critical · from telemetry analysis`}
          tone={data.behavior_counts.critical_high ? 'warn' : 'safe'} />
      </div>

      <div className="panel border-cat-yellow/40">
        <div className="flex items-center gap-2 mb-3">
          <Sparkles size={18} className="text-cat-yellow" />
          <h2 className="font-bold text-cat-yellow">Smart Insights</h2>
          <span className="text-[11px] text-zinc-500">
            (generated from your live tasks, telemetry and predictions — not hardcoded)
          </span>
        </div>
        <ul className="space-y-2">
          {data.insights.map((ins, i) => (
            <li key={i} className="text-sm text-zinc-200 flex gap-2">
              <ChevronRight size={15} className="mt-0.5 shrink-0 text-cat-yellow" /> {ins}
            </li>
          ))}
        </ul>
      </div>

      <TasksTable tasks={data.tasks} navigate={navigate} />
      <TrainingTeaser recs={data.training_recommendations} />
      <ModelFootnote info={data.model_info} />
    </div>
  );
}

function TasksTable({ tasks, navigate }) {
  return (
    <div>
      <SectionTitle title="Today's Scheduled Tasks"
        sub="Select a task to see the AI time prediction, then start the operation." />
      <div className="panel overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-zinc-400 border-b border-cat-line">
              <th className="px-4 py-3">Task</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Machine</th>
              <th className="px-4 py-3">Weather</th>
              <th className="px-4 py-3">Est. (min)</th>
              <th className="px-4 py-3">Predicted (min)</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.task_code}
                  className="border-b border-cat-line/50 hover:bg-zinc-800/40 cursor-pointer"
                  onClick={() => navigate(`/tasks/${t.task_code}`)}>
                <td className="px-4 py-3 font-semibold">{t.task_code}</td>
                <td className="px-4 py-3">{t.task_type}</td>
                <td className="px-4 py-3">{t.machine_id}</td>
                <td className="px-4 py-3">{t.weather}</td>
                <td className="px-4 py-3">{t.estimated_time}</td>
                <td className="px-4 py-3 text-cat-yellow font-semibold">
                  {t.predicted_time ?? '—'}
                </td>
                <td className="px-4 py-3"><Badge>{t.status}</Badge></td>
                <td className="px-4 py-3 text-right text-zinc-500">
                  <ChevronRight size={16} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TrainingTeaser({ recs }) {
  if (!recs.length) return null;
  return (
    <div className="panel">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GraduationCap size={18} className="text-cat-yellow" />
          <h2 className="font-bold">Recommended Training</h2>
        </div>
        <Link to="/training" className="text-xs text-cat-yellow hover:underline">
          Open Training Hub →
        </Link>
      </div>
      <div className="grid sm:grid-cols-3 gap-3">
        {recs.map((r) => (
          <div key={r.module_code}
               className="rounded-lg border border-cat-line p-3 bg-zinc-900/40">
            <div className="flex items-center justify-between">
              <Badge>{r.severity}</Badge>
              <span className="text-[11px] text-zinc-500">
                {r.duration_min} min · {r.format}
              </span>
            </div>
            <div className="font-semibold text-sm mt-2">{r.title}</div>
            <div className="text-xs text-zinc-400 mt-1 line-clamp-3">{r.reason}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ModelFootnote({ info }) {
  return (
    <div className="text-[11px] text-zinc-500 leading-relaxed">
      ML model: {info.algorithm}. Trained on {info.n_real_dataset} supplied Caterpillar +{' '}
      {info.n_synthetic} labelled synthetic rows (estimated time is not an input feature).
      Validation: {info.synth_validation_mae_min} min MAE on a {info.n_synth_validation}-row
      synthetic holdout; {info.loo_mae_real_rows_min} min leave-one-out MAE on the{' '}
      {info.n_real_dataset} real rows — a very small prototype evaluation, not production
      accuracy. Real deployment would require real CAT fleet data.
    </div>
  );
}
