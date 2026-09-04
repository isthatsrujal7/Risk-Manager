import { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function FeedbackLoop() {
  const [status, setStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [retraining, setRetraining] = useState(false);
  const [result, setResult] = useState<any>(null);

  const load = () => {
    api.getFeedbackLoopStatus()
      .then(setStatus)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleRetrain = async () => {
    setRetraining(true);
    setResult(null);
    try {
      const res = await api.triggerRetrain();
      setResult(res);
      await load();
    } catch (e: any) {
      setResult({ error: e.message || 'Retraining failed' });
      console.error(e);
    } finally { setRetraining(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Model Feedback Loop</h1>
          <p className="text-sm text-gray-500 mt-1">Uses human review decisions to retrain and version the fraud model.</p>
        </div>
        <button onClick={handleRetrain} disabled={retraining}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
          {retraining ? 'Retraining...' : 'Retrain Model Now'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Human-labeled rows</p><p className="text-2xl font-bold">{status?.human_labeled_rows}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Total reviews</p><p className="text-2xl font-bold">{status?.total_reviews}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">False positives</p><p className="text-2xl font-bold text-amber-700">{status?.false_positives}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">False negatives</p><p className="text-2xl font-bold text-red-700">{status?.false_negatives}</p></div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Active model version</p>
          <p className="text-xl font-bold text-brand-600 font-mono">{status?.active_model_version}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
          <p className="text-sm text-gray-500">Retrain runs</p>
          <p className="text-xl font-bold">{status?.retrain_history?.length ?? 0}</p>
        </div>
      </div>

      {result && (
        <div className={`rounded-xl border p-6 shadow-sm ${result.error ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
          {result.error ? (
            <p className="font-medium text-red-800">{result.error}</p>
          ) : (
            <div>
              <p className="font-semibold text-green-800">Retraining complete — new model {result.new_model_version}</p>
              <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div className="bg-white rounded-lg p-3 border border-green-200"><p className="text-gray-500">Human rows used</p><p className="font-bold">{result.human_labeled_rows}</p></div>
                <div className="bg-white rounded-lg p-3 border border-green-200"><p className="text-gray-500">Training rows</p><p className="font-bold">{result.training_total_rows}</p></div>
                <div className="bg-white rounded-lg p-3 border border-green-200"><p className="text-gray-500">Best model</p><p className="font-bold">{result.best_model}</p></div>
                <div className="bg-white rounded-lg p-3 border border-green-200"><p className="text-gray-500">Test F1</p><p className="font-bold">{result.test_metrics?.f1}</p></div>
              </div>
            </div>
          )}
        </div>
      )}

      <div>
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Retraining History</h3>
        {(status?.retrain_history?.length ?? 0) === 0 ? (
          <p className="text-gray-500">No retraining runs yet. Trigger a retrain to get started.</p>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Version</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">F1</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Precision</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Recall</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {[...(status?.retrain_history || [])].reverse().map(h => (
                  <tr key={h.version} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-brand-600">{h.version}</td>
                    <td className="px-4 py-3 text-sm">{h.best_model}</td>
                    <td className="px-4 py-3 text-right font-mono font-bold">{h.f1}</td>
                    <td className="px-4 py-3 text-right font-mono">{h.precision}</td>
                    <td className="px-4 py-3 text-right font-mono">{h.recall}</td>
                    <td className="px-4 py-3 text-xs text-gray-400">{h.timestamp ? new Date(h.timestamp).toLocaleString() : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
