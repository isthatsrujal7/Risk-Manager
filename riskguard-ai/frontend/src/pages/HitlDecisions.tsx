import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const BAND_STYLE: Record<string, any> = {
  AI_AUTOPILOT: { ring: 'border-green-200', bg: 'bg-green-50', text: 'text-green-700', chip: 'bg-green-100 text-green-800' },
  HUMAN_REVIEW: { ring: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', chip: 'bg-amber-100 text-amber-800' },
  AI_MANAGED_BLOCK: { ring: 'border-red-200', bg: 'bg-red-50', text: 'text-red-700', chip: 'bg-red-100 text-red-800' },
};

export default function HitlDecisions() {
  const [summary, setSummary] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getHitlSummary(), api.getHitlAlerts(0, 50)])
      .then(([s, a]) => { setSummary(s); setAlerts(a); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Human-in-the-Loop Decisions</h1>
        <p className="text-gray-500 mt-1">Three-tier AI decision system: AI autopilot for low risk, human review for ambiguous, AI block + alert for critical.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {summary?.bands?.map((band: any) => {
          const s = BAND_STYLE[band.band] || {};
          return (
            <div key={band.band} className={`bg-white rounded-xl shadow-sm border ${s.ring} p-6`}>
              <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold ${s.chip} mb-3`}>
                <span>{band.emoji}</span> {band.band.replace(/_/g, ' ')}
              </div>
              <div className="flex items-baseline gap-1">
                <span className="text-4xl font-bold text-gray-900">{band.count}</span>
                <span className="text-sm text-gray-500">({band.pct}%)</span>
              </div>
              <dl className="mt-4 space-y-1.5 text-sm">
                <div className="flex justify-between"><dt className="text-gray-500">Score range</dt><dd className="font-mono font-medium">{band.score_range}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Handled by</dt><dd className="font-medium">{band.handled_by}</dd></div>
                <div className="flex justify-between"><dt className="text-gray-500">Action</dt><dd className="font-medium text-right">{band.action}</dd></div>
              </dl>
              <div className="mt-4 pt-3 border-t border-gray-100 text-xs space-y-1">
                {band.band === 'AI_AUTOPILOT' && <p className="text-gray-500">Auto-allowed: <span className="font-semibold text-green-700">{band.auto_allowed_count}</span></p>}
                {band.band === 'HUMAN_REVIEW' && <p className="text-gray-500">Sent to human: <span className="font-semibold text-amber-700">{band.sent_to_human_count}</span></p>}
                {band.band === 'AI_MANAGED_BLOCK' && <p className="text-gray-500">Alerts raised: <span className="font-semibold text-red-700">{band.alerts_count}</span></p>}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Total assessed</p>
          <p className="text-2xl font-bold text-gray-900">{summary?.total_transactions}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <p className="text-sm text-gray-500">AI-handled (no human)</p>
          <p className="text-2xl font-bold text-green-700">{(summary?.bands?.find((b: any) => b.band === 'AI_AUTOPILOT')?.count ?? 0) + (summary?.bands?.find((b: any) => b.band === 'AI_MANAGED_BLOCK')?.count ?? 0)}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Risk team alerts</p>
          <p className="text-2xl font-bold text-red-700">{summary?.total_alerts}</p>
        </div>
      </div>

      <div>
        <h2 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <span className="text-red-600">🚨</span> Risk Team Alerts (Critical - held by AI)
        </h2>
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {alerts.length === 0 ? (
            <p className="text-center text-gray-500 py-10">No critical alerts. All clear.</p>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Transaction</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Score</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Alert Message</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {alerts.map(a => (
                  <tr key={a.log_id} className="hover:bg-red-50/40">
                    <td className="px-4 py-3">
                      <Link to={`/transactions/${a.transaction_id}`} className="font-mono text-brand-600 hover:underline">{a.transaction_id}</Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500">{a.customer_id}</td>
                    <td className="px-4 py-3 text-right font-medium">₹{a.amount?.toLocaleString()}</td>
                    <td className="px-4 py-3 text-right">
                      <span className="px-2 py-1 rounded-full text-xs font-semibold bg-red-100 text-red-800">{a.final_risk_score?.toFixed(0)}</span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-600 max-w-xs truncate">{a.event_data?.alert_message || a.event_data?.reason}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
