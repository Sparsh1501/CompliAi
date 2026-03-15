import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { UploadProvider } from './context/UploadContext';
import { Toaster } from 'sonner';
import UploadProgressFloat from './components/UploadProgress';
import ErrorBoundary from './components/ErrorBoundary';
import NetworkErrorBanner from './components/NetworkErrorBanner';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Policies from './pages/Policies';
import PolicyDetail from './pages/PolicyDetail';
import Regulations from './pages/Regulations';
import RegulationDetail from './pages/RegulationDetail';
import RegulatoryUpdates from './pages/RegulatoryUpdates';
import GapAnalysis from './pages/GapAnalysis';
import Tasks from './pages/Tasks';
import Evidence from './pages/Evidence';
import Audit from './pages/Audit';
import Departments from './pages/Departments';
import Calendar from './pages/Calendar';
import Chat from './pages/Chat';
import Analytics from './pages/Analytics';
import Checklists from './pages/Checklists';
import Notifications from './pages/Notifications';
import Settings from './pages/Settings';
import LosLms from './pages/LosLms';
import NPCICirculars from './pages/NPCICirculars';
import ComplianceDashboard from './pages/ComplianceDashboard';
import GapAnalysisViewer from './pages/GapAnalysisViewer';
import NotFound from './pages/NotFound';
import Layout from './components/Layout';
import './App.css';

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="app-loading">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return user ? children : <Navigate to="/login" state={{ from: location }} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/dashboard"
        element={
          <PrivateRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/policies"
        element={
          <PrivateRoute>
            <Layout>
              <Policies />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/policies/:policyId"
        element={
          <PrivateRoute>
            <Layout>
              <PolicyDetail />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/regulations"
        element={
          <PrivateRoute>
            <Layout>
              <Regulations />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/regulations/:regulationId"
        element={
          <PrivateRoute>
            <Layout>
              <RegulationDetail />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/regulatory-updates"
        element={
          <PrivateRoute>
            <Layout>
              <RegulatoryUpdates />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/gap-analysis"
        element={
          <PrivateRoute>
            <Layout>
              <GapAnalysis />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/evidence"
        element={
          <PrivateRoute>
            <Layout>
              <Evidence />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/audit"
        element={
          <PrivateRoute>
            <Layout>
              <Audit />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/tasks"
        element={
          <PrivateRoute>
            <Layout>
              <Tasks />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/departments"
        element={
          <PrivateRoute>
            <Layout>
              <Departments />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/calendar"
        element={
          <PrivateRoute>
            <Layout>
              <Calendar />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <PrivateRoute>
            <Layout>
              <Chat />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/analytics"
        element={
          <PrivateRoute>
            <Layout>
              <Analytics />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/checklists"
        element={
          <PrivateRoute>
            <Layout>
              <Checklists />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/notifications"
        element={
          <PrivateRoute>
            <Layout>
              <Notifications />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <PrivateRoute>
            <Layout>
              <Settings />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/los-lms"
        element={
          <PrivateRoute>
            <Layout>
              <LosLms />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/npci-circulars"
        element={
          <PrivateRoute>
            <Layout>
              <NPCICirculars />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/compliance-dashboard"
        element={
          <PrivateRoute>
            <Layout>
              <ComplianceDashboard />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route
        path="/gap-analysis/:analysisId"
        element={
          <PrivateRoute>
            <Layout>
              <GapAnalysisViewer />
            </Layout>
          </PrivateRoute>
        }
      />
      <Route path="/" element={<Navigate to="/dashboard" />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <UploadProvider>
              <NetworkErrorBanner />
              <AppRoutes />
              <UploadProgressFloat />
              <Toaster position="top-right" />
            </UploadProvider>
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
