import { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { api, liveEventsUrl } from '../services/api';

const TIER_BADGE: Record<string, string> = {
  LOW: 'bg-green-100 text-green-800',
  MEDIUM: 'bg-yellow-100 text-yellow-800',
  HIGH: 'bg-orange-100 text-orange-800',
  CRITICAL: 'bg-red-100 text-red-800',
};

export default function LiveFeed() {
  const [events, setEvents] = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [clientCount, setClientCount] = useState(0);
  const [banner, setBanner] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getLiveRecent(20).then(setEvents).catch(console.error);
    api.getLiveStats().then(s => setClientCount(s.connected_clients)).catch(() => {});

    const es = new EventSource(liveEventsUrl());
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'connected') {
          setConnected(true);
          setClientCount(msg.client_count);
        } else if (msg.type === 'new_assessment') {
          setEvents(prev => [msg.data, ...prev].slice(0, 50));
          setBanner(`New transaction ${msg.data.transaction_id} scored ${msg.data.final_risk_score.toFixed(1)} (${msg.data.risk_tier})`);
          setTimeout(() => setBanner(''), 5000);
        }
      } catch { /* ignore */ }
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [events]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Real-time Risk Monitoring</h1>
          <p className="text-sm text-gray-500 mt-1">Live stream of incoming transactions as they are risk-scored.</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-2 text-sm ${connected ? 'text-green-600' : 'text-red-500'}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            {connected ? 'Live' : 'Disconnected'}
          </span>
          <span className="text-sm text-gray-500">{clientCount} viewer(s)</span>
        </div>
      </div>

      {banner && (
        <div className="bg-indigo-50 border border-indigo-200 text-indigo-800 px-4 py-3 rounded-lg text-sm font-medium animate-pulse">
          ⚡ {banner}
        </div>
      )}

      <div ref={listRef} className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-y-auto max-h-[600px]">
        {events.length === 0 ? (
          <p className="text-center text-gray-500 py-12">Waiting for new transactions...</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {events.map((ev, i) => (
              <li key={`${ev.transaction_id}-${i}`} className="px-4 py-3 flex items-center gap-4 hover:bg-gray-50">
                <span className={`h-2 w-2 rounded-full shrink-0 ${ev.risk_tier === 'CRITICAL' ? 'bg-red-500' : ev.risk_tier === 'HIGH' ? 'bg-orange-500' : ev.risk_tier === 'MEDIUM' ? 'bg-yellow-500' : 'bg-green-500'}`} />
                <Link to={`/transactions/${ev.transaction_id}`} className="font-mono text-sm text-brand-600 hover:underline shrink-0">{ev.transaction_id}</Link>
                <span className="font-mono text-xs text-gray-500 shrink-0">{ev.customer_id}</span>
                <span className="text-sm shrink-0">₹{ev.amount?.toLocaleString()}</span>
                <div className="ml-auto flex items-center gap-2">
                  <span className="font-mono text-sm font-bold">{ev.final_risk_score?.toFixed(1)}</span>
                  {ev.risk_tier && <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${TIER_BADGE[ev.risk_tier] || 'bg-gray-100'}`}>{ev.risk_tier}</span>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
