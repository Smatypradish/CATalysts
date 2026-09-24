import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout.jsx';
import { useAuth } from './context.jsx';
import BehaviorAnalysis from './pages/BehaviorAnalysis.jsx';
import Dashboard from './pages/Dashboard.jsx';
import History from './pages/History.jsx';
import IncidentLog from './pages/IncidentLog.jsx';
import Login from './pages/Login.jsx';
import SafetyMonitor from './pages/SafetyMonitor.jsx';
import TaskDetail from './pages/TaskDetail.jsx';
import TrainingHub from './pages/TrainingHub.jsx';
import WhatIfSimulator from './pages/WhatIfSimulator.jsx';

function Protected({ children }) {
  const { operator } = useAuth();
  return operator ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="tasks/:taskCode" element={<TaskDetail />} />
        <Route path="what-if" element={<WhatIfSimulator />} />
        <Route path="safety" element={<SafetyMonitor />} />
        <Route path="behavior" element={<BehaviorAnalysis />} />
        <Route path="training" element={<TrainingHub />} />
        <Route path="incidents" element={<IncidentLog />} />
        <Route path="history" element={<History />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
