import { HardHat, KeyRound, User } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api.js';
import { useAuth } from '../context.jsx';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [operators, setOperators] = useState([]);
  const [operatorId, setOperatorId] = useState('OP1001');
  const [pin, setPin] = useState('1001');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get('/auth/operators').then(({ data }) => setOperators(data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const { data } = await api.post('/auth/login', { operator_id: operatorId, pin });
      login(data);
      navigate('/');
    } catch {
      setError('Invalid operator ID or PIN. Demo: OP1001 / 1001.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-cat-black relative overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-2 bg-cat-yellow" />
      <div className="panel w-full max-w-md shadow-2xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="bg-cat-yellow rounded-lg p-2.5">
            <HardHat size={28} className="text-cat-black" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight">
              <span className="text-cat-yellow">CAT</span> Operator Companion
            </h1>
            <p className="text-xs text-zinc-400">Smart Operator Assistant for CAT Machinery</p>
          </div>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-zinc-400 uppercase">Operator ID</label>
            <div className="relative mt-1">
              <User size={15} className="absolute left-3 top-2.5 text-zinc-500" />
              <select
                className="input pl-9"
                value={operatorId}
                onChange={(e) => {
                  setOperatorId(e.target.value);
                  setPin(e.target.value.replace('OP', ''));
                }}
              >
                {operators.map((o) => (
                  <option key={o.operator_id} value={o.operator_id}>
                    {o.operator_id} — {o.name} ({o.skill})
                  </option>
                ))}
                {operators.length === 0 && <option value="OP1001">OP1001 — Arun Kumar</option>}
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-zinc-400 uppercase">PIN</label>
            <div className="relative mt-1">
              <KeyRound size={15} className="absolute left-3 top-2.5 text-zinc-500" />
              <input
                className="input pl-9"
                type="password"
                value={pin}
                onChange={(e) => setPin(e.target.value)}
                placeholder="e.g. 1001"
              />
            </div>
          </div>
          {error && <div className="text-sm text-red-400">{error}</div>}
          <button className="btn-primary w-full justify-center" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in to shift'}
          </button>
        </form>

        <p className="mt-5 text-[11px] text-zinc-500 leading-relaxed">
          Hackathon prototype. Telemetry shown during operation is simulated;
          historical analysis uses the supplied datasets (machine telemetry +
          task records) loaded from <code>data/*.csv</code>.
        </p>
      </div>
    </div>
  );
}
