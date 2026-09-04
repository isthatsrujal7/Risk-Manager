import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#22c55e', '#3b82f6', '#ef4444', '#eab308'];

export default function ModelAnalytics() {
  const [overview, setOverview] = useState<any>(null);
  const [modelPerf, setModelPerf] = useState<any>(null);
  const [feedback, setFeedback] = useState<any>(null);
  const [errors, setErrors] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getAnalyticsOverview(), api.getModelPerformance(), api.getFeedbackSummary(), api.getErrorPatterns()])
      .then(([o, m, f, e]) => { setOverview(o); setModelPerf(m); setFeedback(f); setErrors(e); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  const cmData = modelPerf?.confusion_matrix ? [
    { name: 'True Neg', value: modelPerf.confusion_matrix[0][0] },
    { name: 'False Pos', value: modelPerf.confusion_matrix[0][1] },
    { name: 'False Neg', value: modelPerf.confusion_matrix[1][0] },
    { name: 'True Pos', value: modelPerf.confusion_matrix[1][1] },
  ] : [];

  const he = modelPerf?.honest_evaluation;
  const co = he?.cost_optimal;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Model Analytics</h1>

      <p className="text-sm text-gray-500 mt-1">All headline metrics are measured on the {overview?.test_samples || 'held-out'} transactions of the chronological test set — a stream this model never trained on.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard title="Precision (held-out)" value={`${((overview?.precision || 0) * 100).toFixed(1)}%`} />
        <MetricCard title="Recall (held-out)" value={`${((overview?.recall || 0) * 100).toFixed(1)}%`} />
        <MetricCard title="F1 Score (held-out)" value={`${((overview?.f1_score || 0) * 100).toFixed(1)}%`} />
        <MetricCard title="FPR (held-out)" value={`${((overview?.false_positive_rate || 0) * 100).toFixed(2)}%`} />
        <MetricCard title="FNR (held-out)" value={`${((overview?.false_negative_rate || 0) * 100).toFixed(2)}%`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
          <p className="text-xs text-gray-500 font-medium">Estimated Prevention Saved</p>
          <p className="text-xl font-bold text-green-700 mt-1">₹{(overview?.cost_saved_total || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
          <p className="text-xs text-gray-400 mt-1">Expected-loss model over {overview?.cost_decisions_computed || 0} scored txns</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
          <p className="text-xs text-gray-500 font-medium">Exposure if All Allowed</p>
          <p className="text-xl font-bold text-red-700 mt-1">₹{(overview?.cost_exposure_if_all_allowed || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
          <p className="text-xs text-gray-400 mt-1">What fraud would cost with no screening</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
          <p className="text-xs text-gray-500 font-medium">Review friction / incident</p>
          <p className="text-xl font-bold text-gray-900 mt-1">₹{overview?.cost_assumptions?.friction_per_review || 0}</p>
          <p className="text-xs text-gray-400 mt-1">Per human-review cost used by the cost engine</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Confusion Matrix</h3>
          {cmData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={cmData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="value" fill="#6366f1">
                  {cmData.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-gray-500">No data available</p>}
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Test Set Performance</h3>
          {modelPerf ? (
            <div className="space-y-3">
              <InfoRow label="Model Type" value={modelPerf.model_type || modelPerf.best_model} />
              <InfoRow label="Total Samples" value={modelPerf.total_samples} />
              <InfoRow label="True Positives" value={modelPerf.true_positives} />
              <InfoRow label="True Negatives" value={modelPerf.true_negatives} />
              <InfoRow label="False Positives" value={modelPerf.false_positives} />
              <InfoRow label="False Negatives" value={modelPerf.false_negatives} />
              <InfoRow label="Precision" value={`${((modelPerf.precision || 0) * 100).toFixed(2)}%`} />
              <InfoRow label="Recall" value={`${((modelPerf.recall || 0) * 100).toFixed(2)}%`} />
              <InfoRow label="F1 Score" value={`${((modelPerf.f1 || modelPerf.f1_score || 0) * 100).toFixed(2)}%`} />
              <InfoRow label="PR-AUC" value={modelPerf.pr_auc?.toFixed(4)} />
            </div>
          ) : <p className="text-gray-500">No metrics available</p>}

          {modelPerf?.all_model_results && (
            <div className="mt-6">
              <h4 className="font-medium text-gray-700 mb-2">Model Comparison</h4>
              <table className="w-full text-sm">
                <thead><tr className="text-gray-500"><th>Model</th><th>P</th><th>R</th><th>F1</th></tr></thead>
                <tbody>
                  {Object.entries(modelPerf.all_model_results).map(([name, m]: [string, any]) => (
                    <tr key={name} className="border-t border-gray-100">
                      <td className="py-2 font-medium">{name.replace('_', ' ')}</td>
                      <td>{((m as any).precision * 100).toFixed(1)}%</td>
                      <td>{((m as any).recall * 100).toFixed(1)}%</td>
                      <td className="font-medium">{(((m as any).f1 || (m as any).f1_score || 0) * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {he && (
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-lg font-semibold text-gray-800">Honest Evaluation</h3>
            <span className={`px-3 py-1 rounded-full text-xs font-bold text-white ${he.leakage_audit?.status === 'PASS' ? 'bg-green-500' : 'bg-red-500'}`}>
              Leakage audit: {he.leakage_audit?.status}
            </span>
          </div>
          <p className="text-sm text-gray-500 mb-4">Self-critical test-set report: chronological split, no train/test ID overlap, bootstrap 95% CIs, and an operating point chosen by cost (₹50 FP vs ₹500 FN), not by a fixed 0.5 threshold.</p>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Split method</p>
              <p className="text-sm font-medium text-gray-800 mt-0.5">{he.split?.method ? he.split.method.split('(')[0].trim() : '-'}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Train overlapping test</p>
              <p className="text-sm font-medium text-gray-800 mt-0.5">{he.leakage_audit?.overlap_count} IDs</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Test samples</p>
              <p className="text-sm font-medium text-gray-800 mt-0.5">{he.threshold_0_5?.total_samples}</p>
            </div>
            <div className="p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">Cost-optimal threshold</p>
              <p className="text-sm font-bold text-brand-600 mt-0.5">{co?.threshold}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg border border-gray-200">
              <h4 className="text-sm font-semibold text-gray-700 mb-3">Fixed threshold (0.5)</h4>
              <InfoRow label="Precision" value={`${((he.threshold_0_5?.precision || 0) * 100).toFixed(1)}%`} />
              <InfoRow label="Recall" value={`${((he.threshold_0_5?.recall || 0) * 100).toFixed(1)}%`} />
              <InfoRow label="F1" value={`${((he.threshold_0_5?.f1 || 0) * 100).toFixed(1)}%`} />
              <InfoRow label="False positives" value={he.threshold_0_5?.fp_count} />
              <InfoRow label="False negatives" value={he.threshold_0_5?.fn_count} />
            </div>
            <div className="p-4 rounded-lg border border-brand-200 bg-brand-50/40">
              <h4 className="text-sm font-semibold text-brand-700 mb-3">Cost-optimal operating point</h4>
              <InfoRow label="Precision" value={`${((co?.precision || 0) * 100).toFixed(1)}% (95% CI ${((co?.precision_ci?.ci_95_low || 0) * 100).toFixed(1)}–${((co?.precision_ci?.ci_95_high || 0) * 100).toFixed(1)}%)`} />
              <InfoRow label="Recall" value={`${((co?.recall || 0) * 100).toFixed(1)}% (95% CI ${((co?.recall_ci?.ci_95_low || 0) * 100).toFixed(1)}–${((co?.recall_ci?.ci_95_high || 0) * 100).toFixed(1)}%)`} />
              <InfoRow label="F1" value={`${((co?.f1 || 0) * 100).toFixed(1)}% (95% CI ${((co?.f1_ci?.ci_95_low || 0) * 100).toFixed(1)}–${((co?.f1_ci?.ci_95_high || 0) * 100).toFixed(1)}%)`} />
              <InfoRow label="False positives" value={co?.fp_count} />
              <InfoRow label="False negatives" value={co?.fn_count} />
              <hr className="my-2" />
              <InfoRow label="Decision cost" value={`₹${(he.threshold_0_5?.total_cost || 0).toLocaleString()} → ₹${(co?.total_cost || 0).toLocaleString()}`} highlight />
            </div>
          </div>

          <p className="text-xs text-gray-400 mt-4">{he.headline}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Feedback Summary</h3>
          {feedback ? (
            <div className="space-y-3">
              <InfoRow label="Total Reviews" value={feedback.total_reviews} />
              <InfoRow label="Approved" value={feedback.approved_count} />
              <InfoRow label="Rejected" value={feedback.rejected_count} />
              <InfoRow label="Escalated" value={feedback.escalated_count} />
              <InfoRow label="False Positives" value={feedback.false_positives} />
              <InfoRow label="False Negatives" value={feedback.false_negatives} />
              <hr />
              <InfoRow label="FP Cost" value={`₹${feedback.total_fp_cost}`} />
              <InfoRow label="FN Cost" value={`₹${feedback.total_fn_cost}`} />
              <InfoRow label="Total Cost" value={`₹${feedback.total_estimated_cost}`} highlight />
            </div>
          ) : <p className="text-gray-500">No feedback data</p>}
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Error Pattern Analysis</h3>
          {errors ? (
            <div className="space-y-4">
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">False Positive Categories</h4>
                {Object.keys(errors.false_positive_patterns || {}).length === 0 ? (
                  <p className="text-sm text-gray-500">No false positive patterns</p>
                ) : (
                  <div className="space-y-1">
                    {Object.entries(errors.false_positive_patterns || {}).map(([cat, count]) => (
                      <div key={cat} className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">{cat}</span>
                        <span className="text-sm font-medium text-orange-600">{count as number}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">False Negative Categories</h4>
                {Object.keys(errors.false_negative_patterns || {}).length === 0 ? (
                  <p className="text-sm text-gray-500">No false negative patterns</p>
                ) : (
                  <div className="space-y-1">
                    {Object.entries(errors.false_negative_patterns || {}).map(([cat, count]) => (
                      <div key={cat} className="flex items-center gap-2">
                        <span className="text-sm text-gray-600">{cat}</span>
                        <span className="text-sm font-medium text-red-600">{count as number}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : <p className="text-gray-500">No error data</p>}
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100 text-center">
      <p className="text-xs text-gray-500 font-medium">{title}</p>
      <p className="text-xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  );
}

function InfoRow({ label, value, highlight }: { label: string; value: any; highlight?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-sm text-gray-600">{label}</span>
      <span className={`text-sm font-medium ${highlight ? 'text-red-600' : 'text-gray-800'}`}>{value}</span>
    </div>
  );
}
