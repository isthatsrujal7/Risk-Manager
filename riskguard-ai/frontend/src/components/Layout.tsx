import { NavLink, Outlet } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { api } from '../services/api';

const navItems = [
  { to: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1' },
  { to: '/transactions', label: 'Transactions', icon: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
  { to: '/reviews', label: 'Review Queue', icon: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' },
  { to: '/hitl', label: 'HITL Decisions', icon: 'M12 8v4m0 4h.01M4.93 19.07a10 10 0 1114.14 0M4.93 19.07L2.5 21.5M19.07 19.07l2.43 2.43' },
  { to: '/spikes', label: 'Fraud Spikes', icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6' },
  { to: '/merchants', label: 'Merchant Risk', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
  { to: '/feedback-loop', label: 'Feedback Loop', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
  { to: '/live', label: 'Live Monitor', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { to: '/alerts', label: 'Alerts', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
  { to: '/analytics', label: 'Model Analytics', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { to: '/fraud-patterns', label: 'Fraud Patterns', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { to: '/audit', label: 'Audit Trail', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
];

export default function Layout() {
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    api.getPendingReviewCount().then(d => setPendingCount(d.pending_count)).catch(() => {});
    const interval = setInterval(() => {
      api.getPendingReviewCount().then(d => setPendingCount(d.pending_count)).catch(() => {});
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-6 border-b border-gray-800">
          <h1 className="text-xl font-bold text-brand-400">RiskGuard AI</h1>
          <p className="text-xs text-gray-400 mt-1">Fraud Detection Platform</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={item.icon} />
              </svg>
              <span>{item.label}</span>
              {item.label === 'Review Queue' && pendingCount > 0 && (
                <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                  {pendingCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-800 text-xs text-gray-500">
          <p>Model: v1.0</p>
          <p>Razorpay Buildathon</p>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
