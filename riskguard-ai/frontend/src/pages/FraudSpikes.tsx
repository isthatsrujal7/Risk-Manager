import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function FraudSpikes() {
  const [detection, setDetection] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [timeseries, setTimeseries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [windowMin, setWindowMin] = useState(60);
  const [zThresh, setZThresh] = useState(3);

  const load = () => {
    Promise.all([
      api.detectFraudSpike({ windowMinutes: windowMin, zThreshold: zThresh }),
      api.getSpikeHistory(50),
      api.getSpikeTimeseries(60, 168),
    ])
      .then(([d, h, t]) => { setDetection(d); setHistory(h); setTimeseries(t); })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [windowMin, zThresh]);

  const handleScan = async () => {
    setScanning(true);
    try {
      const d = await api.detectFraudSpike({ windowMinutes: windowMin, zThreshold: zThresh });
      setDetection(d);
      const h = await api.getSpikeHistory(50);
      setHistory(h);
    } catch (e) { console.error(e); } finally { setScanning(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600" /></div>;

  const chartData = timeseries.map(p => ({ ...p, time: new Date(p.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Fraud Spike Detection</h1>
        <button onClick={handleScan} disabled={scanning}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 disabled:opacity-50">
          {scanning ? 'Scanning...' : 'Run Scan Now'}
        </button>
      </div>
      <p className="text-gray-500 text-sm">Monitors the aggregate suspicious-transaction rate over time and flags sudden spikes vs. the historical baseline using a Z-score test.</p>

      <div className="flex flex-wrap gap-4">
        <label className="text-sm text-gray-600 flex items-center gap-2">
          Window (min)
          <select value={windowMin} onChange={e => setWindowMin(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-2 py-1 text-sm">
            {[15, 30, 60, 120, 240].map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </label>
        <label className="text-sm text-gray-600 flex items-center gap-2">
          Z-threshold
          <select value={zThresh} onChange={e => setZThresh(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-2 py-1 text-sm">
            {[2, 2.5, 3, 3.5, 4].map(z => <option key={z} value={z}>{z}</option>)}
          </select>
        </label>
      </div>

      {detection && (
        <div className={`rounded-xl border p-6 ${detection.is_spike ? 'bg-red-50 border-red-200' : 'bg-white border-gray-100'} shadow-sm`}>
          <div className="flex items-center gap-3 mb-4">
            <span className={`text-3xl ${detection.is_spike ? '' : 'opacity-40'}`}>🚨</span>
            <div>
              <h2 className={`text-lg font-bold ${detection.is_spike ? 'text-red-700' : 'text-gray-800'}`}>
                {detection.is_spike ? 'FRAUD SPIKE DETECTED' : 'No Spike Detected'}
              </h2>
              <p className="text-sm text-gray-500">
                {detection.current_window_suspicious} suspicious / {detection.current_window_total} transactions in the last {detection.window_minutes} min
                ({detection.current_suspicious_rate_pct}%)
              </p>
            </div>
            {detection.z_score !== 0 && (
              <span className={`ml-auto px-3 py-1 rounded-full text-sm font-semibold ${detection.is_spike ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'}`}>
                Z-score: {detection.z_score}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="bg-white rounded-lg p-3 border border-gray-100"><p className="text-gray-500">Hist. avg / window</p><p className="font-bold">{detection.historical_avg_suspicious_per_window}</p></div>
            <div className="bg-white rounded-lg p-3 border border-gray-100"><p className="text-gray-500">Hist. std</p><p className="font-bold">{detection.historical_std}</p></div>
            <div className="bg-white rounded-lg p-3 border border-gray-100"><p className="text-gray-500">Current suspicious</p><p className="font-bold">{detection.current_window_suspicious}</p></div>
            {detection.new_alert_created && <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200"><p className="text-yellow-700 font-medium">Alert persisted to risk team</p></div>}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Suspicious Transaction Volume (last 7 days)</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Line type="monotone" dataKey="total" name="Total" stroke="#6366f1" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="suspicious" name="Suspicious" stroke="#ef4444" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Spike Alert History</h3>
        {history.length === 0 ? (
          <p className="text-gray-500">No spike alerts recorded.</p>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Alert</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Z-score</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Suspicious</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {history.map(a => (
                  <tr key={a.log_id} className="hover:bg-red-50/40">
                    <td className="px-4 py-3 text-xs text-gray-400">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</td>
                    <td className="px-4 py-3 text-sm text-gray-700">{a.alert_message}</td>
                    <td className="px-4 py-3 text-right font-mono text-xs">{a.z_score}</td>
                    <td className="px-4 py-3 text-right font-semibold text-red-700">{a.current_window_suspicious}</td>
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
