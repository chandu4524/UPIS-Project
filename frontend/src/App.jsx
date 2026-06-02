import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Citizens from './pages/Citizens';
import UploadHistory from './pages/UploadHistory';
import PersonProfile from './pages/PersonProfile';
import RelationshipGraph from './pages/RelationshipGraph';
import AuditLogs from './pages/AuditLogs';
import Reports from './pages/Reports';
import ReportPreview from './pages/ReportPreview';
import TemplateMapping from './pages/TemplateMapping';
import ManualReview from './pages/ManualReview';
import OCRProcessing from './pages/OCRProcessing';
import IntelligenceSearch from './pages/IntelligenceSearch';
import AIAssistant from './pages/AIAssistant';
import AdminUsers from './pages/AdminUsers';
import DataSources from './pages/DataSources';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import ToastProvider from './components/ToastProvider';
import './styles/global.css';

export default function App() {
  return (
    <ToastProvider>
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <Upload />
            </ProtectedRoute>
          }
        />
        <Route
          path="/template-mapping"
          element={
            <ProtectedRoute>
              <TemplateMapping />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ocr-processing"
          element={
            <ProtectedRoute>
              <OCRProcessing />
            </ProtectedRoute>
          }
        />
        <Route
          path="/upload-history"
          element={
            <ProtectedRoute>
              <UploadHistory />
            </ProtectedRoute>
          }
        />
        <Route
          path="/citizens"
          element={
            <ProtectedRoute>
              <Citizens />
            </ProtectedRoute>
          }
        />
        <Route
          path="/intelligence-search"
          element={
            <ProtectedRoute>
              <IntelligenceSearch />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ai-assistant"
          element={
            <ProtectedRoute>
              <AIAssistant />
            </ProtectedRoute>
          }
        />
        <Route
          path="/manual-review"
          element={
            <ProtectedRoute>
              <ManualReview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/person-profile/:id"
          element={
            <ProtectedRoute>
              <PersonProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/staging-profile/:stagingId"
          element={
            <ProtectedRoute>
              <PersonProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/uploaded-profile/:uploadId/:rowIndex"
          element={
            <ProtectedRoute>
              <PersonProfile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/relationships/:id"
          element={
            <ProtectedRoute>
              <RelationshipGraph />
            </ProtectedRoute>
          }
        />
        <Route
          path="/audit-logs"
          element={
            <ProtectedRoute>
              <AuditLogs />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports/preview/:type"
          element={
            <ProtectedRoute>
              <ReportPreview />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <Reports />
            </ProtectedRoute>
          }
        />
        <Route
          path="/analytics-dashboard"
          element={
            <ProtectedRoute>
              <AnalyticsDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/data-sources"
          element={
            <ProtectedRoute>
              <DataSources />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin-users"
          element={
            <ProtectedRoute>
              <AdminUsers />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
    </ToastProvider>
  );
}
