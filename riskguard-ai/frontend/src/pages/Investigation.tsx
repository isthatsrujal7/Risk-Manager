import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../services/api';

export default function Investigation() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    api.getInvestigation(id)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (!data) return <div className="text-center py-10 text-gray-500">Investigation not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/transactions" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">Investigation {data.investigation_id}</h1>
        {data.is_llm_generated && <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">LLM Generated</span>}
        {!data.is_llm_generated && <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">Deterministic</span>}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800 mb-3">Summary</h3>
        <p className="text-gray-700 leading-relaxed">{data.summary}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Evidence</h3>
          <div className="space-y-3">
            {(data.evidence || []).map((ev: any, i: number) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">{ev.type}</span>
                  <span className="text-xs px-2 py-0.5 bg-brand-100 text-brand-700 rounded">{ev.source}</span>
                </div>
                <p className="text-sm text-gray-600 mt-1">{ev.description}</p>
                <p className="text-xs text-gray-400 mt-1">Value: {String(ev.value)}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Contributing Factors</h3>
          {(data.contributing_factors || []).length === 0 ? (
            <p className="text-sm text-gray-500">No contributing factors identified.</p>
          ) : (
            <ul className="space-y-2">
              {data.contributing_factors.map((f: string, i: number) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-orange-500 mt-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" /></svg>
                  </span>
                  <span className="text-sm text-gray-700">{f}</span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="text-lg font-semibold text-gray-800 mb-4 mt-6">Behavioral Anomalies</h3>
          {(data.behavioral_anomalies || []).length === 0 ? (
            <p className="text-sm text-gray-500">No behavioral anomalies detected.</p>
          ) : (
            <ul className="space-y-2">
              {data.behavioral_anomalies.map((a: string, i: number) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-purple-500 mt-1">
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M10 2a8 8 0 100 16 8 8 0 000-16zM9 5a1 1 0 112 0v4a1 1 0 11-2 0V5zm1 8a1 1 0 100-2 1 1 0 000 2z" /></svg>
                  </span>
                  <span className="text-sm text-gray-700">{a}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Explanation</h3>
          <p className="text-sm text-gray-700 leading-relaxed">{data.explanation}</p>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Uncertainty</h3>
          <p className="text-sm text-gray-700 leading-relaxed">{data.uncertainty || 'None identified.'}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Related Activity</h3>
        {(data.related_activity || []).length === 0 ? (
          <p className="text-sm text-gray-500">No related activity found.</p>
        ) : (
          <div className="space-y-2">
            {data.related_activity.map((r: any, i: number) => (
              <div key={i} className="flex items-center gap-4 p-3 bg-gray-50 rounded-lg">
                <Link to={`/transactions/${r.transaction_id}`} className="text-brand-600 hover:underline font-mono text-sm">
                  {r.transaction_id}
                </Link>
                <span className="text-sm text-gray-700">₹{r.amount?.toLocaleString()}</span>
                <span className="text-sm text-gray-500">{r.category}</span>
                <span className="text-xs text-gray-400">{r.timestamp ? new Date(r.timestamp).toLocaleString() : '-'}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-brand-50 rounded-xl p-6 border border-brand-200">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">Recommended Action</p>
            <p className="text-2xl font-bold text-brand-700">{data.recommended_action}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-500">Agent Model</p>
            <p className="text-sm font-medium text-gray-700">{data.agent_model_used}</p>
          </div>
        </div>
        {data.review && (
          <div className="mt-4 p-4 bg-white rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Human Decision</p>
            <p className={`text-lg font-bold ${data.review.human_decision === 'APPROVED' ? 'text-green-600' : data.review.human_decision === 'REJECTED' ? 'text-red-600' : 'text-gray-800'}`}>
              {data.review.human_decision || 'Pending'}
            </p>
            {data.review.reviewer_note && <p className="text-sm text-gray-600 mt-1">{data.review.reviewer_note}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
