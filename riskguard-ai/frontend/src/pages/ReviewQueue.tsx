import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

export default function ReviewQueue() {
  const [reviews, setReviews] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [selectedReview, setSelectedReview] = useState<any>(null);
  const [decision, setDecision] = useState('');
  const [note, setNote] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadReviews = () => {
    api.getReviews(0, 100, filter || undefined)
      .then(setReviews)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadReviews(); }, [filter]);

  const handleSubmitDecision = async () => {
    if (!selectedReview || !decision) return;
    setSubmitting(true);
    try {
      await api.submitReview({
        investigation_id: selectedReview.investigation_id,
        transaction_id: selectedReview.transaction_id,
        human_decision: decision,
        reviewer_note: note,
        reviewer_name: 'admin',
      });
      setSelectedReview(null);
      setDecision('');
      setNote('');
      loadReviews();
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  const pending = reviews.filter(r => !r.human_decision);
  const decided = reviews.filter(r => r.human_decision);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Review Queue</h1>

      <div className="flex gap-2">
        {['', 'pending', 'decided'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${filter === f ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}>
            {f || 'All'} {f === 'pending' && pending.length > 0 && `(${pending.length})`}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {reviews.map(r => (
            <div key={r.review_id}
              onClick={() => setSelectedReview(r)}
              className={`bg-white rounded-xl shadow-sm p-4 border cursor-pointer transition ${selectedReview?.review_id === r.review_id ? 'border-brand-500 ring-2 ring-brand-200' : 'border-gray-100 hover:border-gray-200'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-sm text-brand-600">{r.transaction_id}</span>
                  <span className="text-sm text-gray-500">₹{r.amount?.toLocaleString()}</span>
                  <span className="text-sm text-gray-400">{r.customer_id}</span>
                </div>
                <div className="flex items-center gap-2">
                  {r.human_decision ? (
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${r.human_decision === 'APPROVED' ? 'bg-green-100 text-green-800' : r.human_decision === 'REJECTED' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}`}>
                      {r.human_decision}
                    </span>
                  ) : (
                    <span className="px-2 py-1 text-xs font-medium bg-orange-100 text-orange-800 rounded-full">Pending</span>
                  )}
                </div>
              </div>
              <p className="text-sm text-gray-600 mt-2 line-clamp-2">{r.summary}</p>
              <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                <span>AI Recommends: <span className="font-medium text-gray-600">{r.ai_recommendation}</span></span>
                {r.decision_timestamp && <span>Decided: {new Date(r.decision_timestamp).toLocaleString()}</span>}
              </div>
            </div>
          ))}
          {reviews.length === 0 && <p className="text-center text-gray-500 py-8">No reviews found.</p>}
        </div>

        <div className="space-y-6">
          {selectedReview ? (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 sticky top-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Decision Panel</h3>
              <div className="space-y-3 mb-6">
                <div>
                  <p className="text-xs text-gray-500">Transaction</p>
                  <Link to={`/transactions/${selectedReview.transaction_id}`} className="text-brand-600 hover:underline font-mono text-sm">
                    {selectedReview.transaction_id}
                  </Link>
                </div>
                <div>
                  <p className="text-xs text-gray-500">AI Recommendation</p>
                  <p className="font-medium">{selectedReview.ai_recommendation}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Summary</p>
                  <p className="text-sm text-gray-600">{selectedReview.summary}</p>
                </div>
              </div>

              {!selectedReview.human_decision ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Your Decision</label>
                    <div className="grid grid-cols-2 gap-2">
                      {['APPROVED', 'REJECTED', 'ESCALATED', 'UNCERTAIN'].map(d => (
                        <button key={d} onClick={() => setDecision(d)}
                          className={`px-3 py-2 rounded-lg text-sm font-medium border transition ${decision === d ? 'bg-brand-600 text-white border-brand-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>
                          {d}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
                    <textarea value={note} onChange={e => setNote(e.target.value)} rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500"
                      placeholder="Add reviewer note..." />
                  </div>
                  <button onClick={handleSubmitDecision} disabled={!decision || submitting}
                    className="w-full px-4 py-3 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 disabled:opacity-50 transition">
                    {submitting ? 'Submitting...' : 'Submit Decision'}
                  </button>
                </div>
              ) : (
                <div className="p-4 bg-gray-50 rounded-lg">
                  <p className="text-sm text-gray-500">Decision Already Made</p>
                  <p className="font-bold">{selectedReview.human_decision}</p>
                  {selectedReview.reviewer_note && <p className="text-sm text-gray-600 mt-1">{selectedReview.reviewer_note}</p>}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 text-center text-gray-500">
              Select a review to make a decision
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
