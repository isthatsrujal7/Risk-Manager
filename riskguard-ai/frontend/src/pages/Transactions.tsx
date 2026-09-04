import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

const tierColor: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
};

export default function Transactions() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    api.getTransactions(0, 100)
      .then(data => setTransactions(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Transactions</h1>
        <input
          type="text"
          placeholder="Search by ID, customer..."
          value={filter}
          onChange={e => setFilter(e.target.value)}
          className="px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-brand-500 focus:border-transparent"
        />
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Transaction ID</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Customer</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Amount</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Category</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Payment</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Location</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Time</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Actual Fraud</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {transactions
              .filter(t => !filter || t.transaction_id.toLowerCase().includes(filter.toLowerCase()) || t.customer_id.toLowerCase().includes(filter.toLowerCase()))
              .map(t => (
              <tr key={t.transaction_id} className="hover:bg-gray-50">
                <td className="px-4 py-3">
                  <Link to={`/transactions/${t.transaction_id}`} className="text-brand-600 hover:underline font-mono text-sm">
                    {t.transaction_id}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-gray-700">{t.customer_id}</td>
                <td className="px-4 py-3 text-sm font-medium text-gray-900">₹{t.amount.toLocaleString()}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{t.merchant_category || '-'}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{t.payment_method || '-'}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{t.location_city || '-'} ({t.location_country})</td>
                <td className="px-4 py-3 text-sm text-gray-500">{t.timestamp ? new Date(t.timestamp).toLocaleString() : '-'}</td>
                <td className="px-4 py-3">
                  {t.is_fraud ? (
                    <span className="px-2 py-1 text-xs font-medium bg-red-100 text-red-800 rounded-full">Fraud</span>
                  ) : (
                    <span className="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded-full">Legit</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
