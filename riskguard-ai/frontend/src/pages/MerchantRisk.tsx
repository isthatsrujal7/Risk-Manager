import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const TIER_BADGE: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
};

export default function MerchantRisk() {
  const [merchants, setMerchants] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>(null);
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    Promise.all([api.getMerchants(filter || undefined), api.getMerchantSummary()])
      .then(([m, s]) => { setMerchants(m); setSummary(s); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [filter]);

  const openMerchant = async (id: string) => {
    try {
      const d = await api.getMerchant(id);
      setSelected(d);
    } catch (e) { console.error(e); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Merchant Risk Profiles</h1>
        <button onClick={async () => { await api.rebuildMerchantProfiles(); load(); }}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700">
          Rebuild Profiles
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Total Merchants</p><p className="text-2xl font-bold">{summary?.total_merchants}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Avg Risk Score</p><p className="text-2xl font-bold">{summary?.avg_risk_score?.toFixed(1)}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Medium+</p><p className="text-2xl font-bold text-amber-700">{(summary?.tiers?.MEDIUM ?? 0) + (summary?.tiers?.HIGH ?? 0) + (summary?.tiers?.CRITICAL ?? 0)}</p></div>
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100"><p className="text-sm text-gray-500">Critical</p><p className="text-2xl font-bold text-red-700">{summary?.tiers?.CRITICAL ?? 0}</p></div>
      </div>

      <div className="flex gap-2">
        {['', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(t => (
          <button key={t} onClick={() => setFilter(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium ${filter === t ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`}>
            {t || 'All'}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Merchant</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Txns</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Flagged</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Risk Score</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {merchants.map(m => (
                <tr key={m.merchant_id} onClick={() => openMerchant(m.merchant_id)} className="hover:bg-gray-50 cursor-pointer">
                  <td className="px-4 py-3">
                    <span className="font-mono text-brand-600">{m.merchant_id}</span>
                    {m.merchant_name && <span className="text-sm text-gray-500 ml-2">{m.merchant_name}</span>}
                  </td>
                  <td className="px-4 py-3 text-right text-sm">{m.total_transactions}</td>
                  <td className="px-4 py-3 text-right text-sm font-medium text-amber-700">{m.flagged_count}</td>
                  <td className="px-4 py-3 text-right font-mono font-bold">{m.risk_score?.toFixed(0)}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-1 rounded-full text-xs font-semibold ${TIER_BADGE[m.risk_tier] || 'bg-gray-100'}`}>{m.risk_tier}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {merchants.length === 0 && <p className="text-center text-gray-500 py-8">No merchants found.</p>}
        </div>

        <div className="space-y-4">
          {selected ? (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 sticky top-6">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold font-mono text-brand-600">{selected.merchant_id}</h3>
                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${TIER_BADGE[selected.risk_tier] || 'bg-gray-100'}`}>{selected.risk_tier}</span>
              </div>
              {selected.merchant_name && <p className="text-sm text-gray-500">{selected.merchant_name} · {selected.category}</p>}
              <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Total</p><p className="font-bold">{selected.total_transactions}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Amount</p><p className="font-bold">₹{selected.total_amount?.toLocaleString()}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Risk Score</p><p className="font-bold">{selected.risk_score?.toFixed(1)}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Avg Txn Risk</p><p className="font-bold">{selected.avg_risk_score?.toFixed(1)}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Flagged</p><p className="font-bold text-amber-700">{selected.flagged_count}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Critical</p><p className="font-bold text-red-700">{selected.critical_count}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Settlement failures</p><p className="font-bold">{selected.settlement_failure_count}</p></div>
                <div className="p-3 bg-gray-50 rounded-lg"><p className="text-gray-500">Reversals</p><p className="font-bold">{selected.reverse_count}</p></div>
              </div>
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Top Risk Transactions</h4>
                <div className="space-y-2 max-h-72 overflow-auto">
                  {(selected.transactions || []).slice(0, 10).map((t: any) => (
                    <div key={t.transaction_id} className="flex items-center justify-between p-2 border border-gray-100 rounded-lg">
                      <Link to={`/transactions/${t.transaction_id}`} className="font-mono text-xs text-brand-600 hover:underline">{t.transaction_id}</Link>
                      <div className="text-right">
                        <p className="text-xs font-bold">{t.risk_score?.toFixed(0)}</p>
                        <p className="text-[10px] text-gray-400">{t.settlement_status}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 text-center text-gray-500">
              Select a merchant to view risk profile
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
