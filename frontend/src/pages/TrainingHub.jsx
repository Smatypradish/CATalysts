import { CalendarCheck, CheckCircle2, GraduationCap, Link2, MonitorPlay } from 'lucide-react';
import { useEffect, useState } from 'react';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import { Badge, SectionTitle } from '../components/ui.jsx';

export default function TrainingHub() {
  const { operator } = useAuth();
  const [modules, setModules] = useState([]);
  const [recs, setRecs] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [toast, setToast] = useState('');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try {
      const [m, r, a] = await Promise.all([
        api.get('/training/modules'),
        api.get(`/training/recommendations/${operator.operator_id}`),
        api.get(`/training/assignments/${operator.operator_id}`),
      ]);
      setModules(m.data);
      setRecs(r.data);
      setAssignments(a.data);
      setLoaded(true);
    } catch {
      setError('Could not load the Training Hub. Is the backend running on :8001?');
    }
  };
  useEffect(() => { load(); }, []); // eslint-disable-line

  if (error && !loaded) {
    return (
      <div className="panel max-w-xl">
        <p className="text-sm text-red-400">{error}</p>
        <button className="btn-primary mt-4" onClick={load}>Retry</button>
      </div>
    );
  }
  if (!loaded) return <div className="text-zinc-400">Loading training hub…</div>;

  const assign = async (moduleCode, reason) => {
    await api.post('/training/assign', {
      operator_id: operator.operator_id, module_code: moduleCode,
      reason: reason || 'Manual self-enrolment',
    });
    setToast(`Enrolled in ${moduleCode}.`);
    load();
  };

  const complete = async (id) => {
    await api.post(`/training/assignments/${id}/complete`);
    setToast('Module marked as completed. Nice work!');
    load();
  };

  const bookInstructor = async (moduleCode) => {
    const { data } = await api.post('/training/book-instructor', {
      operator_id: operator.operator_id, module_code: moduleCode,
      preferred_slot: 'Next available',
    });
    setToast(`Instructor booked (${data.slot}) for ${data.module.title}. [Simulated]`);
    load();
  };

  const assignedCodes = new Set(
    assignments.filter((a) => a.status === 'Assigned').map((a) => a.module_code));

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-extrabold">Operator Training Hub</h1>
        <p className="text-sm text-zinc-400">
          Recommendations are generated from your detected behavior — not hardcoded.
          Example: excessive idling → "Efficient Idle Management".
        </p>
      </div>

      {toast && <div className="panel border-cat-yellow/50 text-sm text-cat-yellow">{toast}</div>}

      {recs.length > 0 && (
        <div>
          <SectionTitle title="Behaviour-linked recommendations" />
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
            {recs.map((r) => (
              <div key={r.module_code} className="panel border-cat-yellow/40">
                <div className="flex items-center justify-between">
                  <Badge>{r.severity}</Badge>
                  <span className="text-[11px] text-zinc-500">{r.format} · {r.duration_min} min</span>
                </div>
                <div className="font-bold mt-2">{r.title}</div>
                <div className="text-xs text-zinc-400 mt-1 flex gap-1.5">
                  <Link2 size={13} className="shrink-0 mt-0.5" /> {r.reason}
                </div>
                <button
                  className="btn-primary mt-3 w-full justify-center"
                  disabled={assignedCodes.has(r.module_code)}
                  onClick={() => assign(r.module_code, r.reason)}
                >
                  {assignedCodes.has(r.module_code) ? 'Assigned' : 'Assign this module'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <ModulesGrid modules={modules} assignedCodes={assignedCodes}
        assign={assign} bookInstructor={bookInstructor} />
      <AssignmentsTable assignments={assignments} complete={complete} />
    </div>
  );
}

function ModulesGrid({ modules, assignedCodes, assign, bookInstructor }) {
  return (
    <div>
      <SectionTitle title="All training modules"
        sub="E-learning, simulation and instructor-led formats." />
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
        {modules.map((m) => (
          <div key={m.code} className="panel flex flex-col">
            <div className="flex items-center gap-2 text-cat-yellow">
              {m.format === 'instructor' ? <CalendarCheck size={17} />
                : m.format === 'simulation' ? <MonitorPlay size={17} />
                : <GraduationCap size={17} />}
              <span className="text-[11px] uppercase font-semibold">{m.format} · {m.category}</span>
            </div>
            <div className="font-bold mt-2">{m.title}</div>
            <div className="text-xs text-zinc-400 mt-1 flex-1">{m.description}</div>
            <div className="text-[11px] text-zinc-500 mt-2">{m.duration_min} minutes · {m.code}</div>
            <div className="flex gap-2 mt-3">
              <button className="btn-ghost flex-1 justify-center text-xs"
                disabled={assignedCodes.has(m.code)}
                onClick={() => assign(m.code)}>
                {assignedCodes.has(m.code) ? 'Assigned' : 'Enrol'}
              </button>
              {m.format === 'instructor' && (
                <button className="btn-primary flex-1 justify-center text-xs"
                  onClick={() => bookInstructor(m.code)}>
                  Book instructor
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function AssignmentsTable({ assignments, complete }) {
  if (assignments.length === 0) {
    return (
      <div>
        <SectionTitle title="My assignments" />
        <div className="panel text-sm text-zinc-400">No assignments yet.</div>
      </div>
    );
  }
  return (
    <div>
      <SectionTitle title="My assignments" />
      <div className="panel p-0 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-zinc-400 border-b border-cat-line">
              <th className="px-4 py-2">Module</th>
              <th className="px-4 py-2">Reason</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={a.id} className="border-b border-cat-line/40">
                <td className="px-4 py-2 font-semibold">{a.module_title}</td>
                <td className="px-4 py-2 text-xs text-zinc-400 max-w-md">{a.reason}</td>
                <td className="px-4 py-2"><Badge>{a.status}</Badge></td>
                <td className="px-4 py-2 text-right">
                  {a.status === 'Assigned' && (
                    <button className="btn-ghost text-xs" onClick={() => complete(a.id)}>
                      <CheckCircle2 size={13} /> Mark complete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
