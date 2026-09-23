export function StatCard({ icon: Icon, label, value, sub, tone = 'default' }) {
  const tones = {
    default: 'text-cat-yellow',
    safe: 'text-emerald-400',
    warn: 'text-amber-400',
    danger: 'text-red-400',
  };
  return (
    <div className="panel flex items-start gap-3">
      {Icon && (
        <div className={`mt-0.5 ${tones[tone]}`}>
          <Icon size={22} />
        </div>
      )}
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wide text-zinc-400">{label}</div>
        <div className="text-xl font-bold truncate">{value}</div>
        {sub && <div className="text-xs text-zinc-400 mt-1">{sub}</div>}
      </div>
    </div>
  );
}

const badgeTones = {
  CRITICAL: 'bg-red-600/20 text-red-300 border-red-600/50',
  HIGH: 'bg-orange-600/20 text-orange-300 border-orange-600/50',
  WARNING: 'bg-amber-600/20 text-amber-300 border-amber-600/50',
  MEDIUM: 'bg-amber-600/20 text-amber-300 border-amber-600/50',
  LOW: 'bg-zinc-600/20 text-zinc-300 border-zinc-500/50',
  INFO: 'bg-sky-600/20 text-sky-300 border-sky-600/50',
  SAFE: 'bg-emerald-600/20 text-emerald-300 border-emerald-600/50',
  Scheduled: 'bg-sky-600/20 text-sky-300 border-sky-600/50',
  'In Progress': 'bg-amber-600/20 text-amber-300 border-amber-600/50',
  Completed: 'bg-emerald-600/20 text-emerald-300 border-emerald-600/50',
  Open: 'bg-red-600/20 text-red-300 border-red-600/50',
  Acknowledged: 'bg-amber-600/20 text-amber-300 border-amber-600/50',
  Resolved: 'bg-emerald-600/20 text-emerald-300 border-emerald-600/50',
  Assigned: 'bg-sky-600/20 text-sky-300 border-sky-600/50',
  dataset: 'bg-cat-yellow/15 text-cat-yellow border-cat-yellow/40',
  synthetic: 'bg-purple-600/20 text-purple-300 border-purple-600/50',
  simulated: 'bg-zinc-600/20 text-zinc-300 border-zinc-500/50',
};

export function Badge({ children, tone }) {
  const cls = badgeTones[tone] || badgeTones[String(children)] || badgeTones.INFO;
  return (
    <span className={`inline-block rounded-md border px-2 py-0.5 text-[11px] font-semibold ${cls}`}>
      {children}
    </span>
  );
}

export function SectionTitle({ title, sub }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold text-cat-yellow">{title}</h2>
      {sub && <p className="text-sm text-zinc-400 mt-0.5">{sub}</p>}
    </div>
  );
}

export function Empty({ text }) {
  return <div className="panel text-sm text-zinc-400 text-center py-8">{text}</div>;
}
