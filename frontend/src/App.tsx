import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import { ToastProvider } from './components/Toast';
import { ConfirmProvider } from './components/ConfirmProvider';
import { AuthProvider, useAuth } from './contexts/AuthContext';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const ProjectList = lazy(() => import('./pages/ProjectList'));
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'));
const TodoDetail = lazy(() => import('./pages/TodoDetail'));
const ExperienceList = lazy(() => import('./pages/ExperienceList'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const Organizations = lazy(() => import('./pages/Organizations'));
const Templates = lazy(() => import('./pages/Templates'));

function PageLoading() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-6 py-4">
        <div className="h-5 w-5 animate-pulse rounded bg-border/50" />
        <div className="h-4 w-32 animate-pulse rounded bg-border/50" />
      </div>
      <div className="flex-1 p-6">
        <div className="mb-4 h-5 w-48 animate-pulse rounded bg-border/50" />
        <div className="mb-3 h-4 w-full animate-pulse rounded bg-border/50" />
        <div className="h-4 w-3/4 animate-pulse rounded bg-border/50" />
      </div>
    </div>
  );
}

function RequireAuth() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-bg-primary">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <ToastProvider>
            <ConfirmProvider>
            <Suspense fallback={<PageLoading />}>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route element={<RequireAuth />}>
                  <Route element={<Layout />}>
                    <Route path="/" element={<ErrorBoundary><ProjectList /></ErrorBoundary>} />
                    <Route path="/todo/:id" element={<ErrorBoundary><TodoDetail /></ErrorBoundary>} />
                    <Route path="/project/:id" element={<ErrorBoundary><ProjectDetail /></ErrorBoundary>} />
                    <Route path="/experience" element={<ErrorBoundary><ExperienceList /></ErrorBoundary>} />
                    <Route path="/organizations" element={<ErrorBoundary><Organizations /></ErrorBoundary>} />
                    <Route path="/templates" element={<ErrorBoundary><Templates /></ErrorBoundary>} />
                    <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Route>
                </Route>
              </Routes>
            </Suspense>
            </ConfirmProvider>
          </ToastProvider>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
