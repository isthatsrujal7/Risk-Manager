import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Link } from 'react-router-dom';

const severityColors: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800 border-green-200',
  MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  HIGH: 'bg-orange-100 text-orange-800 border-orange-200',
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
};

const riskColors: Record<string, string> = {
  ALLOW: 'bg-green-100 text-green-800',
  REVIEW: 'bg-yellow-100 text-yellow-800',
  HOLD: 'bg-red-100 text-red-800',
  VERIFY: 'bg-blue-100 text-blue-800',
};

export default function FraudPatterns() {
  const [summary, setSummary] = useState<any>(null);
  const [templates, setTemplates] = useState<any>(null);
  const [transactions, setTransactions] = useState<any[]>([]);
  const [detected, setDetected] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activePatterns, setActivePatterns] = useState<Record<string, any[]>>({});
  const [selectedTxn, setSelectedTxn] = useState<string>('');

  useEffect(() => {
    Promise.all([
      api.getPatternSummary(),
      api.getPatternTemplates(),
    ])
      .then(([s, t]) => { setSummary(s); setTemplates(t); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api.getTransactions(0, 50)
      .then(async (txns) => {
        setTransactions(txns);
        const patternMap: Record<string, any[]> = {};
        for (const t of txns.slice(0, 20)) {
          try {
            const patterns = await api.getPatternsForTransaction(t.transaction_id);
            if (patterns.length > 0) patternMap[t.transaction_id] = patterns;
          } catch {}
        }
        setActivePatterns(patternMap);
      })
      .catch(console.error);
  }, []);

  const handleDetect = async (txnId: string) => {
    setSelectedTxn(txnId);
    try {
      const result = await api.detectPatterns(txnId);
      setDetected(result);
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  const typeCounts = summary?.patterns_by_type || {};
  const severityCounts = summary?.patterns_by_severity || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Fraud Behavior Patterns</h1>
      <p className="text-gray-600 text-sm max-w-3xl">
        Detects transaction fraud patterns where payments may appear successful but {''}
        <span className="font-semibold">the merchant never receives the money</span> — including payment collapse,
        status mismatch, ghost payments, settlement delays, and more.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <SummaryCard title="Total Patterns" value={summary?.total_patterns || 0} color="text-brand-600" />
        <SummaryCard title="Merchant Risk" value={summary?.merchant_risk_count || 0} color="text-red-600" />
        <SummaryCard title="Customer Risk" value={summary?.customer_risk_count || 0} color="text-orange-600" />
        <SummaryCard title="Critical Severity" value={severityCounts?.CRITICAL || 0} color="text-red-700" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Patterns by Type</h3>
          {Object.keys(typeCounts).length === 0 ? (
            <p className="text-gray-500">Run detection to see patterns</p>
          ) : (
            <div className="space-y-3">
              {Object.entries(typeCounts).map(([type, count]) => {
                const tpl = summary?.templates?.[type];
                return (
                  <div key={type} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-gray-800">{tpl?.name || type}</p>
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">{tpl?.description}</p>
                    </div>
                    <span className="px-2 py-1 text-xs font-medium bg-brand-100 text-brand-700 rounded-full">{String(count)}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Transaction Pattern Check</h3>
          <select
            value={selectedTxn}
            onChange={e => handleDetect(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500"
          >
            <option value="">Select a transaction to detect patterns...</option>
            {transactions.map(t => (
              <option key={t.transaction_id} value={t.transaction_id}>
                {t.transaction_id} - ₹{t.amount?.toLocaleString()} ({t.is_fraud ? 'Fraud' : 'Normal'})
              </option>
            ))}
          </select>

          {detected && (
            <div className="mt-4 space-y-3">
              <div className={`p-4 rounded-lg border ${detected.classification === 'NORMAL' ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
                <p className="text-sm text-gray-500">Classification</p>
                <p className={`text-xl font-bold ${detected.classification === 'NORMAL' ? 'text-green-700' : 'text-red-700'}`}>
                  {detected.patterns?.length > 0 ? detected.patterns[0]?.name || detected.classification : detected.classification}
                </p>
                <p className="text-sm text-gray-600 mt-1">{detected.summary}</p>
              </div>

              {detected.patterns?.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-gray-700">Detected Patterns</h4>
                  {detected.patterns.map((p: any, i: number) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="text-sm font-medium">{p.name}</p>
                        <p className="text-xs text-gray-500">Confidence: {p.confidence * 100}%</p>
                      </div>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${severityColors[p.severity] || severityColors.MEDIUM}`}>
                        {p.severity}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {detected.patterns?.length > 0 && (
                <div className="flex justify-between items-center p-3 bg-white border border-gray-200 rounded-lg">
                  <span className="text-sm text-gray-600">Recommended Action</span>
                  <span className={`px-3 py-1 text-sm font-bold rounded-full ${riskColors[detected.recommended_action] || 'bg-gray-100'}`}>
                    {detected.recommended_action}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Transactions With Detected Patterns</h3>
        {Object.keys(activePatterns).length === 0 ? (
          <p className="text-gray-500">No patterns detected on recent transactions. Run detection above.</p>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Transaction</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Pattern</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Severity</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Risk Type</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {Object.entries(activePatterns).map(([txnId, patterns]) => (
                patterns.map((p, i) => (
                  <tr key={`${txnId}-${i}`}>
                    <td className="px-4 py-3">
                      <Link to={`/transactions/${txnId}`} className="text-brand-600 hover:underline font-mono text-sm">{txnId}</Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">{p.pattern_name}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${severityColors[p.severity] || severityColors.MEDIUM}`}>{p.severity}</span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {p.is_merchant_risk ? <span className="text-red-600 font-medium">Merchant</span> : ''}
                      {p.is_customer_risk ? <span className="text-orange-600 font-medium">Customer</span> : ''}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${riskColors[p.recommended_action] || 'bg-gray-100'}`}>{p.recommended_action}</span>
                    </td>
                  </tr>
                ))
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Fraud Pattern Playbook</h3>
        {templates && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(templates).map(([key, tpl]: [string, any]) => (
              <div key={key} className={`p-4 rounded-xl border-2 ${severityColors[tpl.severity] || 'border-gray-200'}`}>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900">{tpl.name}</h4>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${severityColors[tpl.severity] || 'bg-gray-100'}`}>
                    {tpl.severity}
                  </span>
                </div>
                <p className="text-sm text-gray-700">{tpl.description}</p>
                <div className="mt-3 p-3 bg-white/50 rounded-lg">
                  <p className="text-xs font-medium text-gray-500 mb-1">Example:</p>
                  <p className="text-sm text-gray-600">{tpl.example}</p>
                </div>
                <p className="text-xs text-gray-500 mt-2"><span className="font-medium">Impact:</span> {tpl.business_impact}</p>
                <div className="mt-2">
                  <p className="text-xs font-medium text-gray-500 mb-1">Detection Signals:</p>
                  <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                    {tpl.detection_signals?.map((s: string, i: number) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ title, value, color }: { title: string; value: number; color: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
      <p className="text-sm text-gray-500 font-medium">{title}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
