import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const SEVERITY_BADGE: Record<string, string> = {
  LOW: 'bg-gray-100 text-gray-700',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
};

const STATUS_BADGE: Record<string, string> = {
  OPEN: 'bg-blue-100 text-blue-800',
  ACKNOWLEDGED: 'bg-amber-100 text-amber-800',
  RESOLVED: 'bg-green-100 text-green-800',
};

export default function Alerts() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<any>(null);
  const [note, setNote] = useState('');
  const [assignee, setAssignee] = useState('');

  const load = () => {
    Promise.all([api.getAlerts(filter || undefined), api.getAlertSummary()])
      .then(([a, s]) => { setAlerts(a); setSummary(s); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const handleAction = async (status: string) => {
    if (!selected) return;
    try {
      if (status === 'RESOLVED') {
        await api.resolveAlert(selected.alert_id, { assigned_to: assignee || undefined, resolution_note: note });
      } else {
        await api.acknowledgeAlert(selected.alert_id, { status, assigned_to: assignee || undefined, resolution_note: note });
      }
      setSelected(null); setNote(''); setAssignee('');
      load();
    } catch (e) { console.error(e); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Alert System</h1>
        <p className="text-sm text-gray-500 mt-1">Risk team alerts with acknowledge / resolve workflow. External delivery via webhook/slack/email when configured.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Open</p><p className="text-2xl font-bold text-blue-700">{summary?.open}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Acknowledged</p><p className="text-2xl font-bold text-amber-700">{summary?.acknowledged}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Resolved</p><p className="text-2xl font-bold text-green-700">{summary?.resolved}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Critical</p><p className="text-2xl font-bold text-red-700">{summary?.by_severity?.CRITICAL ?? 0}</p></div>
      </div>

      <div className="flex gap-2">
        {['', 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${filter === s ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}>
            {s || 'All'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {alerts.length === 0 ? (
            <p className="text-center text-gray-500 py-10">No alerts found.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {alerts.map(a => (
                <li key={a.alert_id} onClick={() => setSelected(a)}
                  className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${selected?.alert_id === a.alert_id ? 'bg-brand-50' : ''}`}>
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-semibold ${SEVERITY_BADGE[a.severity] || 'bg-gray-100'}`}>{a.severity}</span>
                    <span className="font-medium text-gray-800 text-sm">{a.title}</span>
                    <span className={`ml-auto px-2 py-1 rounded-full text-xs font-semibold ${STATUS_BADGE[a.status] || 'bg-gray-100'}`}>{a.status}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1 line-clamp-1">{a.message}</p>
                  <div className="flex items-center gap-4 mt-1 text-xs text-gray-400">
                    <span>{a.source}</span>
                    {a.transaction_id && <Link to={`/transactions/${a.transaction_id}`} className="text-brand-600 hover:underline font-mono">{a.transaction_id}</Link>}
                    <span>{a.created_at ? new Date(a.created_at).toLocaleString() : ''}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-4">
          {selected ? (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 sticky top-6">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-gray-800 font-mono">{selected.alert_id}</h3>
                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${STATUS_BADGE[selected.status]}`}>{selected.status}</span>
              </div>
              <p className="text-sm text-gray-700 mt-3">{selected.message}</p>
              <div className="mt-4 space-y-2 text-sm">
                <div><p className="text-xs text-gray-500">Source</p><p className="font-medium">{selected.source}</p></div>
                <div><p className="text-xs text-gray-500">Severity</p><p className="font-medium">{selected.severity}</p></div>
                {selected.assigned_to && <div><p className="text-xs text-gray-500">Assigned</p><p>{selected.assigned_to}</p></div>}
                {selected.resolution_note && <div><p className="text-xs text-gray-500">Note</p><p>{selected.resolution_note}</p></div>}
              </div>
              {selected.status !== 'RESOLVED' && (
                <div className="mt-4 space-y-3">
                  <input value={assignee} onChange={e => setAssignee(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="Assign to (optional)" />
                  <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" placeholder="Note (optional)" />
                  <div className="flex gap-2">
                    <button onClick={() => handleAction('ACKNOWLEDGED')} className="flex-1 px-3 py-2 bg-amber-500 text-white rounded-lg text-sm font-medium hover:bg-amber-600">Acknowledge</button>
                    <button onClick={() => handleAction('RESOLVED')} className="flex-1 px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700">Resolve</button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 text-center text-gray-500">
              Select an alert to acknowledge or resolve
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
