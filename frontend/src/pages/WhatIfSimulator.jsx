import {
  ArrowRight, Copy, FlaskConical, Fuel, Info, Timer, TriangleAlert,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import api from '../api.js';
import { Badge, SectionTitle } from '../components/ui.jsx';

const DEFAULT_BASELINE = {
  task_type: 'Earth Excavation', weather: 'Sunny', operator_skill: 'Intermediate',
  machine_age: 5, workload_pct: 100, idle_pct: 10,
};

// Provenance tags: ML = model-predicted, SIM = simulated prototype layer.
const ML = <Badge tone="dataset">ML · model-predicted</Badge>;
const SIM = <Badge tone="simulated">SIM · simulated</Badge>;

const inputCls = 'input mt-1';

function Select({ label, badge, value, onChange, options }) {
  return (
    <label className="block">
      <span className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-zinc-400">
        {label} {badge}
      </span>
      <select className={inputCls} value={value}
        onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

function Slider({ label, badge, value, onChange, min, max, unit }) {
  return (
    <label className="block">
      <span className="flex items-center justify-between text-[11px] uppercase tracking-wide text-zinc-400">
        <span className="flex items-center gap-1.5">{label} {badge}</span>
        <b className="text-zinc-200">{value}{unit}</b>
      </span>
      <input type="range" className="w-full mt-1 accent-[#FFCD11]" min={min} max={max}
        value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function ResultRow({ label, badge, value, sub }) {
  return (
    <div className="flex items-center justify-between gap-2 py-1.5 border-b border-cat-line last:border-0">
      <span className="text-xs text-zinc-400 flex items-center gap-1.5">{label} {badge}</span>
      <span className="text-right">
        <b className="text-sm">{value}</b>
        {sub && <div className="text-[10px] text-zinc-500">{sub}</div>}
      </span>
    </div>
  );
}

const outcomeTone = { LOW: 'SAFE', MEDIUM: 'WARNING', HIGH: 'CRITICAL' };

// Effect-dimension tags: productivity (throughput) vs clock-time, plus an
// amber Risk note when a time saving comes with an overload penalty.
const effectCls = {
  productivity: 'border-sky-500/50 text-sky-300',
  time: 'border-zinc-500/60 text-zinc-300',
};

function EffectTag({ kind, label }) {
  return (
    <span className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] font-semibold shrink-0 ${effectCls[kind] || effectCls.time}`}>
      {label}
    </span>
  );
}

function ScenarioCard({ title, accent, inputs, onChange, result, opts, onCopy }) {
  const set = (k) => (v) => onChange({ ...inputs, [k]: v });
  return (
    <div className={`panel space-y-3 ${accent ? 'border-cat-yellow/60' : ''}`}>
      <div className="flex items-center justify-between">
        <h3 className={`font-bold ${accent ? 'text-cat-yellow' : 'text-zinc-300'}`}>{title}</h3>
        {onCopy && (
          <button className="btn-ghost !px-2 !py-1 text-xs" onClick={onCopy}>
            <Copy size={13} /> Copy baseline →
          </button>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Select label="Task type" badge={ML} value={inputs.task_type}
          onChange={set('task_type')} options={opts.task_types} />
        <Select label="Weather" badge={ML} value={inputs.weather}
          onChange={set('weather')} options={opts.weathers} />
        <Select label="Operator skill" badge={ML} value={inputs.operator_skill}
          onChange={set('operator_skill')} options={opts.skills} />
        <Slider label="Machine age" badge={ML} value={inputs.machine_age}
          onChange={set('machine_age')} min={opts.machine_age.min}
          max={opts.machine_age.max} unit=" yrs" />
        <Slider label="Workload" badge={SIM} value={inputs.workload_pct}
          onChange={set('workload_pct')} min={opts.workload_pct.min}
          max={opts.workload_pct.max} unit="%" />
        <Slider label="Idle time" badge={SIM} value={inputs.idle_pct}
          onChange={set('idle_pct')} min={opts.idle_pct.min}
          max={opts.idle_pct.max} unit="%" />
      </div>
      {result && (
        <div className="rounded-lg bg-zinc-900/60 border border-cat-line px-3 py-1.5">
          <ResultRow label="Predicted duration" badge={ML}
            value={`${result.model_predicted_min} min`}
            sub="model output, before workload/idle" />
          <ResultRow label="Total clock time" badge={SIM}
            value={`${result.total_clock_min} min`}
            sub={`${result.productive_min} min work + ${result.idle_min} min idle`} />
          <ResultRow label="Estimated fuel" badge={SIM}
            value={`${result.fuel_l} L`} sub="prototype burn model" />
          <ResultRow label="Operating outcome" badge={SIM}
            value={<Badge tone={outcomeTone[result.outcome.level]}>{result.outcome.label}</Badge>} />
        </div>
      )}
    </div>
  );
}


function DeltaCard({ icon: Icon, label, diff, badge }) {
  const better = diff.abs_diff < 0;
  const worse = diff.abs_diff > 0;
  const cls = better ? 'text-emerald-400' : worse ? 'text-red-400' : 'text-zinc-300';
  return (
    <div className="panel !p-4 flex items-center gap-3">
      <Icon size={20} className="text-cat-yellow shrink-0" />
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-zinc-400 flex items-center gap-1.5">
          {label} {badge}
        </div>
        <div className={`text-lg font-extrabold ${cls}`}>
          {diff.abs_diff > 0 ? '+' : ''}{diff.abs_diff} {diff.unit}
          {diff.pct_diff != null && (
            <span className="text-sm font-semibold"> ({diff.pct_diff > 0 ? '+' : ''}{diff.pct_diff}%)</span>
          )}
        </div>
        <div className="text-[11px] text-zinc-500">
          {diff.baseline} → {diff.scenario} {diff.unit}
        </div>
      </div>
    </div>
  );
}

function ComparisonStrip({ comparison }) {
  const oc = comparison.outcome_change;
  const ocCls = oc.improved ? 'text-emerald-400'
    : oc.from === oc.to ? 'text-zinc-300' : 'text-red-400';
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <DeltaCard icon={Timer} label="Duration change" badge={SIM}
        diff={comparison.duration} />
      <DeltaCard icon={Fuel} label="Fuel change" badge={SIM}
        diff={comparison.fuel} />
      <div className="panel !p-4 flex items-center gap-3">
        <TriangleAlert size={20} className="text-cat-yellow shrink-0" />
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wide text-zinc-400 flex items-center gap-1.5">
            Outcome change {SIM}
          </div>
          <div className={`text-lg font-extrabold flex items-center gap-2 flex-wrap ${ocCls}`}>
            {oc.from === oc.to ? oc.to : (
              <>{oc.from} <ArrowRight size={16} /> {oc.to}</>
            )}
          </div>
          <div className="text-[11px] text-zinc-500">
            {oc.improved ? 'improved operating band' : oc.from === oc.to ? 'unchanged band' : 'worsened operating band'}
          </div>
        </div>
      </div>
    </div>
  );
}



export default function WhatIfSimulator() {
  const [opts, setOpts] = useState(null);
  const [baseline, setBaseline] = useState(DEFAULT_BASELINE);
  const [scenario, setScenario] = useState(DEFAULT_BASELINE);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [searchParams] = useSearchParams();
  const debounce = useRef(null);

  // Input domains from the trained model's encoder; optional ?task=CODE prefill.
  useEffect(() => {
    api.get('/prediction/what-if/options').then(({ data }) => {
      setOpts(data);
      const code = searchParams.get('task');
      if (!code) return;
      api.get(`/tasks/${code}`).then(({ data: t }) => {
        const pre = {
          task_type: data.task_types.includes(t.task_type) ? t.task_type : data.task_types[0],
          weather: data.weathers.includes(t.weather) ? t.weather : data.weathers[0],
          operator_skill: data.skills.includes(t.operator_skill) ? t.operator_skill : data.skills[0],
          machine_age: Math.round(t.machine?.age_years ?? 5),
          workload_pct: 100, idle_pct: 10,
        };
        setBaseline(pre);
        setScenario(pre);
      }).catch(() => {});
    }).catch(() => setError('Could not load What-If options — is the backend running?'));
  }, [searchParams]);

  // Debounced auto-compare whenever either scenario changes.
  useEffect(() => {
    if (!opts) return;
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      api.post('/prediction/what-if', { baseline, scenario })
        .then(({ data }) => { setResult(data); setError(''); })
        .catch((e) => setError(e.response?.data?.detail || 'Comparison failed'));
    }, 250);
    return () => clearTimeout(debounce.current);
  }, [baseline, scenario, opts]);

  if (!opts) {
    return <div className="text-zinc-400">{error || 'Loading What-If Simulator…'}</div>;
  }

  const cmp = result?.comparison;

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <SectionTitle
          title="What-If Simulator"
          sub="Compare a baseline plan against a what-if scenario using the same trained task-time model — no data is written."
        />
        <div className="flex items-center gap-2 text-[11px]">
          {ML} {SIM}
        </div>
      </div>

      {cmp && <ComparisonStrip comparison={cmp} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ScenarioCard title="BASELINE" inputs={baseline} onChange={setBaseline}
          result={result?.baseline} opts={opts} />
        <ScenarioCard title="WHAT-IF SCENARIO" accent inputs={scenario}
          onChange={setScenario} result={result?.scenario} opts={opts}
          onCopy={() => setScenario(baseline)} />
      </div>

      {error && <div className="panel border-red-600/50 text-sm text-red-300">{error}</div>}

      {cmp && cmp.top_factors.length > 0 && (
        <div className="panel">
          <h3 className="font-bold text-cat-yellow mb-1 flex items-center gap-2">
            <FlaskConical size={16} /> Top factors behind the change
          </h3>
          <p className="text-xs text-zinc-500 mb-3">
            Each factor is tagged by what it changes: <b className="text-sky-300">Productivity effect</b> (throughput),{' '}
            <b className="text-zinc-300">Time effect</b> (clock time) — minute contributions sum to the total
            duration change. A <b className="text-amber-300">Risk effect</b> note appears when a time saving
            comes with an overload penalty, so negative minutes are not automatically "better".
          </p>
          <ul className="space-y-2">
            {cmp.top_factors.map((f, i) => (
              <li key={i} className="text-sm flex items-start gap-2">
                <span className={`font-semibold shrink-0 ${f.risk_note ? 'text-amber-300' : f.impact_min > 0 ? 'text-red-300' : f.impact_min < 0 ? 'text-emerald-300' : 'text-zinc-400'}`}>
                  {f.impact_min > 0 ? '+' : ''}{f.impact_min} min
                </span>
                {f.source === 'model' ? ML : SIM}
                {f.effect && <EffectTag kind={f.effect} label={f.effect_label} />}
                <span>
                  <b>{f.factor}</b> — {f.detail}
                  {f.risk_note && (
                    <span className="flex items-start gap-1 text-xs text-amber-300 mt-0.5">
                      <TriangleAlert size={12} className="mt-0.5 shrink-0" /> {f.risk_note}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result && (
        <div className="panel border-zinc-700">
          <h3 className="font-bold text-zinc-300 mb-2 flex items-center gap-2">
            <Info size={15} className="text-cat-yellow" /> Provenance & prototype assumptions
          </h3>
          <ul className="text-xs text-zinc-400 space-y-1.5">
            <li><b className="text-cat-yellow">Model-predicted:</b> {result.provenance.model_predicted}</li>
            <li><b className="text-purple-300">Simulated:</b> {result.provenance.simulated}</li>
            <li><b className="text-zinc-200">Assumptions:</b> productive burn{' '}
              {result.provenance.assumptions.productive_burn_l_h_at_100pct_workload} L/h at 100% workload,
              idle burn {result.provenance.assumptions.idle_burn_l_h} L/h;{' '}
              {result.provenance.assumptions.workload_effect};{' '}
              {result.provenance.assumptions.idle_effect}.</li>
            <li className="text-zinc-500">{result.provenance.assumptions.note} {result.model.disclaimer}</li>
          </ul>
        </div>
      )}
    </div>
  );
}

