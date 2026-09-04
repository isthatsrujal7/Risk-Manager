import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import TransactionDetail from './pages/TransactionDetail';
import Investigation from './pages/Investigation';
import ReviewQueue from './pages/ReviewQueue';
import ModelAnalytics from './pages/ModelAnalytics';
import AuditTrail from './pages/AuditTrail';
import FraudPatterns from './pages/FraudPatterns';
import HitlDecisions from './pages/HitlDecisions';
import FraudSpikes from './pages/FraudSpikes';
import MerchantRisk from './pages/MerchantRisk';
import LiveFeed from './pages/LiveFeed';
import Alerts from './pages/Alerts';
import FeedbackLoop from './pages/FeedbackLoop';
import { getToken } from './services/api';

function RequireAuth({ children }: { children: JSX.Element }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="transactions/:id" element={<TransactionDetail />} />
          <Route path="investigation/:id" element={<Investigation />} />
          <Route path="reviews" element={<ReviewQueue />} />
          <Route path="analytics" element={<ModelAnalytics />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="fraud-patterns" element={<FraudPatterns />} />
          <Route path="hitl" element={<HitlDecisions />} />
          <Route path="spikes" element={<FraudSpikes />} />
          <Route path="merchants" element={<MerchantRisk />} />
          <Route path="live" element={<LiveFeed />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="feedback-loop" element={<FeedbackLoop />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}