import {
  ArrowLeft, CheckCircle2, CirclePlay, CloudRain, Clock3, Info, Timer,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import api from '../api.js';
import { Badge, StatCard } from '../components/ui.jsx';

export default function TaskDetail() {
  const { taskCode } = useParams();
  const navigate = useNavigate();
  const [task, setTask] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [busy, setBusy] = useState('');
  const [done, setDone] = useState(null);

  const load = () => api.get(`/tasks/${taskCode}`).then(({ data }) => setTask(data));
  useEffect(() => { load(); }, [taskCode]);

  if (!task) return <div className="text-zinc-400">Loading task…</div>;

  const predict = async () => {
    setBusy('predict');
    try {
      const { data } = await api.post(`/tasks/${taskCode}/predict`);
      setPrediction(data);
      await load();
    } finally { setBusy(''); }
  };

  const start = async () => {
    setBusy('start');
    try {
      await api.post(`/tasks/${taskCode}/start`);
      await load();
      navigate('/safety');
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not start task');
    } finally { setBusy(''); }
  };

  const complete = async () => {
    setBusy('complete');
    try {
      const { data } = await api.post(`/tasks/${taskCode}/complete`, {});
      setDone(data);
      await load();
    } finally { setBusy(''); }
  };

  const history = task.history || {};
  const variance = task.actual_time != null && task.predicted_time != null
    ? (task.actual_time - task.predicted_time).toFixed(1) : null;

  return (
    <div className="space-y-6 max-w-5xl">
      <Link to="/" className="text-xs text-zinc-400 hover:text-cat-yellow flex items-center gap-1">
        <ArrowLeft size={14} /> Back to dashboard
      </Link>

      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-extrabold">
            {task.task_code} — {task.task_type}
          </h1>
          <p className="text-sm text-zinc-400">
            {task.site} · Machine {task.machine_id}
            {task.machine && ` (${task.machine.model}, age ${task.machine.age_years} yrs)`}
            {' '}· Operator skill: {task.operator_skill}
          </p>
        </div>
        <Badge>{task.status}</Badge>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={Clock3} label="Planner estimate" value={`${task.estimated_time} min`} />
        <StatCard icon={Timer} label="AI prediction"
          value={task.predicted_time ? `${task.predicted_time} min` : '—'}
          sub={prediction ? `ideal conditions: ${prediction.ideal_conditions_min} min` : ''} />
        <StatCard icon={CloudRain} label="Weather" value={task.weather}
          sub="adverse weather tightens safety thresholds" />
        <StatCard icon={Info} label="Historical actuals"
          value={history.samples ? `${history.avg_actual_min} min avg` : '—'}
          sub={history.samples ? `${history.samples} records (${history.min_actual}–${history.max_actual} min)` : 'no history'} />
      </div>

      {task.status === 'Scheduled' && (
        <div className="flex gap-3">
          <button className="btn-primary" onClick={predict} disabled={!!busy}>
            {busy === 'predict' ? 'Predicting…' : 'Predict completion time'}
          </button>
          <button className="btn-ghost" onClick={start} disabled={!!busy}>
            <CirclePlay size={16} /> Start operation (opens Safety Monitor)
          </button>
        </div>
      )}
      {task.status === 'In Progress' && (
        <div className="flex gap-3">
          <Link to="/safety" className="btn-primary">Go to live Safety Monitor</Link>
          <button className="btn-ghost" onClick={complete} disabled={!!busy}>
            <CheckCircle2 size={16} />
            {busy === 'complete' ? 'Completing…' : 'Complete task'}
          </button>
        </div>
      )}
      {task.status === 'Completed' && variance != null && (
        <div className="panel border-emerald-600/40">
          <h3 className="font-bold text-emerald-400 mb-2">Task completed — predicted vs actual</h3>
          <div className="text-sm space-y-1">
            <div>Predicted: <b className="text-cat-yellow">{task.predicted_time} min</b>
              {' '}· Planner estimate: {task.estimated_time} min
              {' '}· Actual (simulated): <b>{task.actual_time} min</b></div>
            <div className={variance > 0 ? 'text-amber-300' : 'text-emerald-300'}>
              Variance: {variance > 0 ? '+' : ''}{variance} min
              {variance > 0
                ? ' — overran prediction; check behavior findings (idling/low-load) for causes.'
                : ' — completed within prediction. Good work.'}
            </div>
            {done?.note && <div className="text-[11px] text-zinc-500">{done.note}</div>}
          </div>
        </div>
      )}

      {prediction && (
        <div className="panel">
          <h3 className="font-bold text-cat-yellow mb-1">Why this prediction?</h3>
          <p className="text-xs text-zinc-500 mb-3">
            Counterfactual factor analysis: each factor is measured against ideal conditions
            (sunny, expert operator, 1-year-old machine), holding task type constant.
          </p>
          <ul className="space-y-2">
            {prediction.factors.map((f, i) => (
              <li key={i} className="text-sm flex gap-2">
                <span className="text-cat-yellow font-semibold shrink-0">
                  {f.impact_min > 0 ? `+${f.impact_min} min` : '±0'}
                </span>
                <span><b>{f.factor}</b> — {f.detail}</span>
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-zinc-500 mt-4">{prediction.model.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
