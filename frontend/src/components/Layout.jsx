import {
  Activity, Bot, ClipboardList, FlaskConical, GraduationCap, HardHat,
  History, LayoutDashboard, LogOut, RotateCcw, ShieldAlert, TriangleAlert,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';
import AssistantDrawer from './AssistantDrawer.jsx';

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/safety', label: 'Safety Monitor', icon: ShieldAlert },
  { to: '/behavior', label: 'Behavior Analysis', icon: Activity },
  { to: '/what-if', label: 'What-If Simulator', icon: FlaskConical },
  { to: '/training', label: 'Training Hub', icon: GraduationCap },
  { to: '/incidents', label: 'Incident Log', icon: ClipboardList },
  { to: '/history', label: 'History', icon: History },
];

export default function Layout() {
  const { operator, logout } = useAuth();
  const navigate = useNavigate();
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [safety, setSafety] = useState(null);
  const [resetting, setResetting] = useState(false);

  const resetDemo = async () => {
    if (!window.confirm('Reset the demo? All incidents, progress and sessions will be reseeded.')) return;
    setResetting(true);
    try {
      await api.post('/admin/reseed');
      window.location.href = '/login';
    } catch {
      setResetting(false);
    }
  };

  // Poll safety status so critical alerts appear immediately, app-wide.
  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const { data } = await api.get(`/safety/status/${operator.operator_id}`);
        if (!cancelled) setSafety(data);
      } catch { /* server starting */ }
    };
    poll();
    const t = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(t); };
  }, [operator.operator_id]);

  const critical = safety?.critical_incidents > 0;

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 bg-cat-steel border-r border-cat-line flex flex-col">
        <div className="px-5 py-5 border-b border-cat-line">
          <div className="flex items-center gap-2">
            <div className="bg-cat-yellow rounded-md p-1.5">
              <HardHat size={20} className="text-cat-black" />
            </div>
            <div>
              <div className="font-extrabold tracking-tight leading-4">
                <span className="text-cat-yellow">CAT</span> Operator
              </div>
              <div className="text-[11px] text-zinc-400">Companion</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-cat-yellow text-cat-black'
                    : 'text-zinc-300 hover:bg-zinc-800'
                }`
              }
            >
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-cat-line">
          <button
            onClick={() => setAssistantOpen(true)}
            className="w-full btn-ghost justify-center mb-2"
          >
            <Bot size={16} className="text-cat-yellow" /> Smart Assistant
          </button>
          <div className="text-xs text-zinc-400 px-1">
            <div className="font-semibold text-zinc-200">{operator.name}</div>
            <div>{operator.operator_id} · {operator.skill}</div>
          </div>
          <button
            onClick={resetDemo}
            disabled={resetting}
            className="mt-2 flex items-center gap-2 text-xs text-zinc-400 hover:text-cat-yellow px-1"
          >
            <RotateCcw size={13} /> {resetting ? 'Reseeding…' : 'Reset demo data'}
          </button>
          <button
            onClick={() => { logout(); navigate('/login'); }}
            className="mt-2 flex items-center gap-2 text-xs text-zinc-400 hover:text-red-400 px-1"
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0 flex flex-col">
        {critical && (
          <div className="bg-red-600 text-white px-5 py-2.5 flex items-center gap-2 text-sm font-semibold">
            <TriangleAlert size={18} className="animate-pulse" />
            CRITICAL SAFETY ALERT ACTIVE — {safety.latest?.[0]?.type}: check the Safety Monitor immediately.
          </div>
        )}
        <div className="flex-1 p-6 overflow-y-auto">
          <Outlet context={{ safety }} />
        </div>
      </main>

      <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}
