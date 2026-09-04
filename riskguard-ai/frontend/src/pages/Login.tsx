import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, setSession } from '../services/api';

const demoAccounts = [
  { username: 'riskadmin', role: 'Admin', note: 'Model retraining, settings' },
  { username: 'riskanalyst', role: 'Analyst', note: 'Review queue, alerts, feedback' },
  { username: 'riskviewer', role: 'Viewer', note: 'Read-only dashboards' },
];

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError('');
    try {
      const res = await api.login(username.trim(), password);
      setSession(res.access_token, res.user);
      navigate('/');
    } catch (err: any) {
      setError(err.message?.startsWith('API Error 401') ? 'Invalid username or password' : (err.message || 'Login failed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
          <div className="bg-gray-900 px-8 py-8 text-center">
            <h1 className="text-2xl font-bold text-brand-400">RiskGuard AI</h1>
            <p className="text-sm text-gray-400 mt-1">Role-based access control · Fraud Detection Platform</p>
          </div>
          <form onSubmit={handleSubmit} className="px-8 py-8 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="riskanalyst"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="••••••••"
              />
            </div>
            {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
            <button
              type="submit"
              disabled={busy || !username || !password}
              className="w-full py-2.5 bg-brand-600 text-white rounded-lg text-sm font-semibold hover:bg-brand-700 disabled:opacity-50"
            >
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
        <div className="mt-4 bg-white/5 border border-white/10 rounded-xl p-4">
          <p className="text-xs font-semibold text-gray-300 uppercase tracking-wide mb-2">Demo accounts (password format)</p>
          <div className="space-y-1.5">
            {demoAccounts.map(a => (
              <p key={a.username} className="text-xs text-gray-400 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => { setUsername(a.username); setPassword(`RiskGuard@${a.username}`); }}
                  className="text-left font-mono text-brand-400 hover:underline"
                >
                  RiskGuard@{a.username}
                </button>
                <span>· {a.role} — {a.note}</span>
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}