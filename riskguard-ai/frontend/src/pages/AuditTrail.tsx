import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Link } from 'react-router-dom';

const eventColors: Record<string, string> = {
  risk_scored: 'bg-blue-100 text-blue-800',
  investigation_created: 'bg-purple-100 text-purple-800',
  review_decision: 'bg-green-100 text-green-800',
  outcome_recorded: 'bg-yellow-100 text-yellow-800',
};

export default function AuditTrail() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  useEffect(() => {
    api.getAuditTrail(undefined, 0, 200)
      .then(setLogs)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  const filtered = logs.filter(l => {
    if (filter && l.transaction_id && !l.transaction_id.toLowerCase().includes(filter.toLowerCase())) return false;
    if (typeFilter && l.event_type !== typeFilter) return false;
    return true;
  });

  const eventTypes = [...new Set(logs.map(l => l.event_type))];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Audit Trail</h1>

      <div className="flex gap-3">
        <input
          type="text"
          placeholder="Filter by transaction ID..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500"
        />
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500">
          <option value="">All Event Types</option>
          {eventTypes.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Time</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Event Type</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Transaction</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Model Version</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map(log => (
              <tr key={log.log_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                  {log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${eventColors[log.event_type] || 'bg-gray-100 text-gray-800'}`}>
                    {log.event_type}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {log.transaction_id ? (
                    <Link to={`/transactions/${log.transaction_id}`} className="text-brand-600 hover:underline font-mono text-sm">
                      {log.transaction_id}
                    </Link>
                  ) : <span className="text-gray-400">-</span>}
                </td>
                <td className="px-4 py-3 text-sm text-gray-500">{log.model_version || '-'}</td>
                <td className="px-4 py-3">
                  <details className="group">
                    <summary className="text-sm text-brand-600 cursor-pointer hover:underline">View</summary>
                    <pre className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 overflow-auto max-h-48 border border-gray-100">
                      {JSON.stringify(log.event_data, null, 2)}
                    </pre>
                  </details>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && <p className="text-center py-8 text-gray-500">No audit logs found.</p>}
      </div>
    </div>
  );
}
