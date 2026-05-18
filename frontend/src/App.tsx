import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import TodoDetail from './pages/TodoDetail';
import ExperienceList from './pages/ExperienceList';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import SettingsPage from './pages/SettingsPage';
import { ToastProvider } from './components/Toast';

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<ErrorBoundary><ProjectList /></ErrorBoundary>} />
              <Route path="/todo/:id" element={<ErrorBoundary><TodoDetail /></ErrorBoundary>} />
              <Route path="/project/:id" element={<ErrorBoundary><ProjectDetail /></ErrorBoundary>} />
              <Route path="/experience" element={<ErrorBoundary><ExperienceList /></ErrorBoundary>} />
              <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
