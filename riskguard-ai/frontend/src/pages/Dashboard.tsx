import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { Link } from 'react-router-dom';

const TIER_COLORS: Record<string, string> = {
  LOW: '#22c55e',
  MEDIUM: '#eab308',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
};

export default function Dashboard() {
  const [overview, setOverview] = useState<any>(null);
  const [riskTrends, setRiskTrends] = useState<any>(null);
  const [hitl, setHitl] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = () =>
      Promise.all([api.getAnalyticsOverview(), api.getRiskTrends(), api.getHitlSummary()])
        .then(([o, t, h]) => { setOverview(o); setRiskTrends(t); setHitl(h); })
        .catch(console.error)
        .finally(() => setLoading(false));
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;
  if (!overview) return <div className="text-center py-10 text-gray-500">Failed to load data</div>;

  const distData = Object.entries(overview.risk_distribution || {}).map(([name, value]) => ({ name, value }));
  const trendData = (riskTrends?.trends || []).slice(-14);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 text-xs text-green-600 font-medium">
            <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" /> Auto-refreshing (15s)
          </span>
          <span className="text-sm text-gray-500">Model: {overview.model_version}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Transactions Analyzed" value={overview.total_transactions.toLocaleString()} color="blue" />
        <StatCard title="High Risk Cases" value={overview.high_risk_count} color="red" />
        <StatCard title="Precision (held-out test)" value={`${(overview.precision * 100).toFixed(1)}%`} color="green" />
        <StatCard title="Recall (held-out test)" value={`${(overview.recall * 100).toFixed(1)}%`} color="purple" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard title="False Positive Rate" value={`${(overview.false_positive_rate * 100).toFixed(2)}%`} color="yellow" />
        <StatCard title="False Negatives" value={overview.fn_count} color="red" />
        <StatCard title="Estimated Cost" value={`₹${overview.total_cost.toLocaleString()}`} color="orange" />
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-800">Human-in-the-Loop Decisions</h3>
          <Link to="/hitl" className="text-sm text-brand-600 hover:underline">View all →</Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(hitl?.bands || []).map((band: any) => (
            <div key={band.band} className={`rounded-lg p-4 border ${band.band === 'AI_AUTOPILOT' ? 'bg-green-50 border-green-200' : band.band === 'AI_MANAGED_BLOCK' ? 'bg-red-50 border-red-200' : 'bg-amber-50 border-amber-200'}`}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{band.emoji} {band.band.replace(/_/g, ' ')}</span>
                <span className="text-xs text-gray-500 font-mono">{band.score_range}</span>
              </div>
              <p className="text-2xl font-bold text-gray-900 mt-2">{band.count} <span className="text-sm font-normal text-gray-500">({band.pct}%)</span></p>
              <p className="text-xs text-gray-600 mt-1">Handled by: <span className="font-medium">{band.handled_by}</span></p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Risk Distribution</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={distData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }) => `${name}: ${value}`}>
                {distData.map((entry) => (
                  <Cell key={entry.name} fill={TIER_COLORS[entry.name] || '#8884d8'} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Risk Score Trends</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="high" fill="#f97316" name="High" />
              <Bar dataKey="critical" fill="#ef4444" name="Critical" />
              <Bar dataKey="medium" fill="#eab308" name="Medium" />
              <Bar dataKey="low" fill="#22c55e" name="Low" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Business Cost Analysis (Simulated)</h3>
          <div className="space-y-3">
            <div className="flex justify-between"><span className="text-gray-600">False Positives</span><span className="font-medium">{overview.fp_count} incidents</span></div>
            <div className="flex justify-between"><span className="text-gray-600">FP Cost per Incident</span><span className="font-medium">₹{overview.fp_cost_per_incident}</span></div>
            <div className="flex justify-between"><span className="text-gray-600">Total FP Cost</span><span className="font-medium text-orange-600">₹{overview.total_fp_cost.toLocaleString()}</span></div>
            <hr />
            <div className="flex justify-between"><span className="text-gray-600">False Negatives</span><span className="font-medium">{overview.fn_count} incidents</span></div>
            <div className="flex justify-between"><span className="text-gray-600">FN Cost per Incident</span><span className="font-medium">₹{overview.fn_cost_per_incident}</span></div>
            <div className="flex justify-between"><span className="text-gray-600">Total FN Cost</span><span className="font-medium text-red-600">₹{overview.total_fn_cost.toLocaleString()}</span></div>
            <hr />
            <div className="flex justify-between text-lg font-bold"><span>Total Estimated Cost</span><span className="text-red-700">₹{overview.total_cost.toLocaleString()}</span></div>
            <p className="text-xs text-gray-400 mt-2">* Simulated cost model. FP cost = unnecessary intervention. FN cost = potential fraud loss.</p>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h3>
          <div className="space-y-3">
            <Link to="/transactions" className="block p-4 bg-gray-50 rounded-lg hover:bg-brand-50 border border-gray-200 hover:border-brand-300 transition">
              <span className="font-medium text-gray-800">View Transactions</span>
              <p className="text-sm text-gray-500 mt-1">Browse and investigate flagged transactions</p>
            </Link>
            <Link to="/reviews" className="block p-4 bg-gray-50 rounded-lg hover:bg-brand-50 border border-gray-200 hover:border-brand-300 transition">
              <span className="font-medium text-gray-800">Review Queue</span>
              <p className="text-sm text-gray-500 mt-1">Process pending human reviews</p>
            </Link>
            <Link to="/analytics" className="block p-4 bg-gray-50 rounded-lg hover:bg-brand-50 border border-gray-200 hover:border-brand-300 transition">
              <span className="font-medium text-gray-800">Model Analytics</span>
              <p className="text-sm text-gray-500 mt-1">View precision, recall, and error analysis</p>
            </Link>
            <Link to="/audit" className="block p-4 bg-gray-50 rounded-lg hover:bg-brand-50 border border-gray-200 hover:border-brand-300 transition">
              <span className="font-medium text-gray-800">Audit Trail</span>
              <p className="text-sm text-gray-500 mt-1">Track all system events and decisions</p>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, color }: { title: string; value: string | number; color: string }) {
  const colorMap: Record<string, string> = {
    blue: 'border-blue-500 bg-blue-50',
    red: 'border-red-500 bg-red-50',
    green: 'border-green-500 bg-green-50',
    purple: 'border-purple-500 bg-purple-50',
    yellow: 'border-yellow-500 bg-yellow-50',
    orange: 'border-orange-500 bg-orange-50',
  };
  return (
    <div className={`bg-white rounded-xl shadow-sm p-5 border-l-4 ${colorMap[color] || colorMap.blue}`}>
      <p className="text-sm text-gray-500 font-medium">{title}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  );
}
