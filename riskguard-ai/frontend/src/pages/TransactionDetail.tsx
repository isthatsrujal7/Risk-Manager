import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';

const tierBg: Record<string, string> = {
  LOW: 'bg-green-500', MEDIUM: 'bg-yellow-500', HIGH: 'bg-orange-500', CRITICAL: 'bg-red-500',
};

export default function TransactionDetail() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [fraudPatterns, setFraudPatterns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [investigating, setInvestigating] = useState(false);

  useEffect(() => {
    if (!id) return;
    Promise.all([api.getTransaction(id), api.getAuditForTransaction(id), api.getPatternsForTransaction(id)])
      .then(([d, a, fp]) => { setData(d); setAuditLogs(a); setFraudPatterns(fp); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  const handleInvestigate = async () => {
    if (!id) return;
    setInvestigating(true);
    try {
      const result = await api.runInvestigation(id);
      if (result.investigation_id) {
        window.location.href = `/investigation/${result.investigation_id}`;
      }
    } catch (e) {
      console.error(e);
    } finally {
      setInvestigating(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (!data) return <div className="text-center py-10 text-gray-500">Transaction not found</div>;

  const txn = data.transaction;
  const ra = data.risk_assessment;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/transactions" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">Transaction {txn.transaction_id}</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Transaction Details</h3>
            <div className="grid grid-cols-2 gap-4">
              <Info label="Amount" value={`₹${txn.amount.toLocaleString()}`} />
              <Info label="Customer" value={txn.customer_id} />
              <Info label="Payment Method" value={txn.payment_method || '-'} />
              <Info label="Merchant" value={txn.merchant_name || '-'} />
              <Info label="Category" value={txn.merchant_category || '-'} />
              <Info label="Device" value={txn.device_id || '-'} />
              <Info label="Location" value={`${txn.location_city || '-'}, ${txn.location_country}`} />
              <Info label="Time" value={txn.timestamp ? new Date(txn.timestamp).toLocaleString() : '-'} />
              <Info label="IP Address" value={txn.ip_address || '-'} />
              <Info label="Actual Fraud" value={txn.is_fraud ? 'YES' : 'NO'} />
            </div>
          </div>

          {ra && (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Risk Assessment</h3>
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="text-center">
                  <p className="text-sm text-gray-500">ML Score</p>
                  <p className="text-2xl font-bold">{ra.ml_risk_score.toFixed(1)}</p>
                  <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                    <div className={`h-2 rounded-full ${ra.ml_risk_score > 60 ? 'bg-red-500' : ra.ml_risk_score > 30 ? 'bg-yellow-500' : 'bg-green-500'}`} style={{ width: `${ra.ml_risk_score}%` }} />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">Behavioral Deviation</p>
                  <p className="text-2xl font-bold">{ra.behavioral_deviation_score.toFixed(1)}</p>
                  <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                    <div className={`h-2 rounded-full ${ra.behavioral_deviation_score > 60 ? 'bg-red-500' : 'bg-yellow-500'}`} style={{ width: `${ra.behavioral_deviation_score}%` }} />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">Final Score</p>
                  <p className="text-2xl font-bold text-brand-600">{ra.final_risk_score.toFixed(1)}</p>
                </div>
                <div className="text-center">
                  <p className="text-sm text-gray-500">Risk Tier</p>
                  <span className={`inline-block px-3 py-1 rounded-full text-white text-sm font-medium ${tierBg[ra.risk_tier] || 'bg-gray-500'}`}>
                    {ra.risk_tier}
                  </span>
                </div>
              </div>
              <div className="mb-4">
                <p className="text-sm text-gray-500">Recommended Action: <span className="font-semibold text-gray-800">{ra.recommended_action}</span></p>
              </div>
              {ra.hitl_band && (
                <div className={`mb-4 p-3 rounded-lg border ${ra.hitl_band === 'AI_AUTOPILOT' ? 'bg-green-50 border-green-200' : ra.hitl_band === 'AI_MANAGED_BLOCK' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
                  <p className="text-xs font-medium uppercase text-gray-500 mb-1">HITL Handling</p>
                  <p className={`font-semibold ${ra.hitl_band === 'AI_AUTOPILOT' ? 'text-green-700' : ra.hitl_band === 'AI_MANAGED_BLOCK' ? 'text-red-700' : 'text-amber-700'}`}>
                    {ra.hitl_band === 'AI_AUTOPILOT' ? '🤖 Handled automatically by AI (score 0-25)' :
                     ra.hitl_band === 'AI_MANAGED_BLOCK' ? '🚨 AI blocked & held + risk team alerted (score 90-100)' :
                     '👤 Sent for human review (score 25-90)'}
                  </p>
                  <p className="text-sm text-gray-600 mt-1">Handled by: <span className="font-medium">{ra.handling_user}</span>{ra.needs_alert ? ' · Alert raised' : ''}</p>
                </div>
              )}
              {ra.top_signals?.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-700 mb-2">Top Signals</h4>
                  <div className="space-y-2">
                    {ra.top_signals.map((s: any, i: number) => (
                      <div key={i} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                        <span className="text-sm font-medium text-gray-600">{i + 1}.</span>
                        <span className="text-sm text-gray-800">{s.description}</span>
                        <span className="ml-auto text-xs text-gray-400">weight: {s.weight}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {fraudPatterns.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Fraud Behavior Patterns Detected</h3>
              <div className="space-y-3">
                {fraudPatterns.map((p: any) => (
                  <div key={p.pattern_id} className={`p-4 rounded-lg border-2 ${p.severity === 'CRITICAL' ? 'border-red-300 bg-red-50' : p.severity === 'HIGH' ? 'border-orange-300 bg-orange-50' : p.severity === 'MEDIUM' ? 'border-yellow-300 bg-yellow-50' : 'border-green-200 bg-green-50'}`}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-gray-900">{p.pattern_name}</span>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${p.severity === 'CRITICAL' ? 'bg-red-500 text-white' : p.severity === 'HIGH' ? 'bg-orange-500 text-white' : p.severity === 'MEDIUM' ? 'bg-yellow-500 text-white' : 'bg-green-500 text-white'}`}>
                        {p.severity}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1">{p.explanation}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>Confidence: <span className="font-medium">{Math.round(p.confidence * 100)}%</span></span>
                      <span>{p.is_merchant_risk && <span className="text-red-600 font-medium">Merchant Risk</span>}</span>
                      <span>{p.is_customer_risk && <span className="text-orange-600 font-medium">Customer Risk</span>}</span>
                      <span>Action: <span className="font-medium text-gray-700">{p.recommended_action}</span></span>
                    </div>
                    {p.signals?.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <p className="text-xs font-medium text-gray-500 mb-1">Detection Signals:</p>
                        <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                          {p.signals.map((s: any, i: number) => (
                            <li key={i}>{s.description}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Audit Timeline</h3>
            {auditLogs.length === 0 ? (
              <p className="text-sm text-gray-500">No audit events recorded.</p>
            ) : (
              <div className="space-y-3">
                {auditLogs.map((log: any) => (
                  <div key={log.log_id} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                    <div className="w-2 h-2 rounded-full bg-brand-500 mt-2 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-gray-800">{log.event_type}</p>
                      <p className="text-xs text-gray-500">{log.timestamp ? new Date(log.timestamp).toLocaleString() : '-'}</p>
                      {log.event_data && Object.keys(log.event_data).length > 0 && (
                        <pre className="text-xs text-gray-600 mt-1 bg-white p-2 rounded border border-gray-100 overflow-auto max-h-32">
                          {JSON.stringify(log.event_data, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Actions</h3>
            <button
              onClick={handleInvestigate}
              disabled={investigating}
              className="w-full px-4 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50 transition"
            >
              {investigating ? 'Investigating...' : 'Run AI Investigation'}
            </button>
          </div>

          {ra && (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Feature Contributions</h3>
              <div className="space-y-2">
                {Object.entries(ra.feature_contributions || {}).map(([key, val]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-sm text-gray-600 w-24">{key}</span>
                    <div className="flex-1 bg-gray-200 rounded-full h-2">
                      <div className="bg-brand-500 h-2 rounded-full" style={{ width: `${(val as number) * 100}%` }} />
                    </div>
                    <span className="text-xs text-gray-500 w-10 text-right">{((val as number) * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 font-medium">{label}</p>
      <p className="text-sm text-gray-800">{value}</p>
    </div>
  );
}
