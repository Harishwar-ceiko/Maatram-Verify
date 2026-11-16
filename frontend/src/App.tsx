import { Navigate, Route, Routes, Link } from "react-router-dom";
import { ProtectedRoute, PublicOnlyRoute } from "./components/ProtectedRoute";
import { Brand, Spinner } from "./components/ui";
import { useAuth, landingFor } from "./lib/auth";
import { LoginPage } from "./pages/auth/LoginPage";
import { RegisterPage } from "./pages/auth/RegisterPage";
import { OverviewPage } from "./pages/student/OverviewPage";
import { ApplicationsPage } from "./pages/student/ApplicationsPage";
import { NewApplicationPage } from "./pages/student/NewApplicationPage";
import { ApplicationDetailPage } from "./pages/student/ApplicationDetailPage";
import { AdminOverviewPage } from "./pages/admin/AdminOverviewPage";
import { AdminApplicationsPage } from "./pages/admin/AdminApplicationsPage";
import { ReviewQueuePage } from "./pages/admin/ReviewQueuePage";
import { AccuracyPage } from "./pages/admin/AccuracyPage";
import { AuditPage } from "./pages/admin/AuditPage";

function HomeRedirect() {
  const { user, state } = useAuth();
  if (state === "loading") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Spinner label="Loading Maatram Verify" />
      </div>
    );
  }
  return <Navigate to={user ? landingFor(user.role) : "/login"} replace />;
}

function NotFoundPage() {
  return (
    <div className="grid min-h-dvh place-items-center px-6">
      <div className="grid justify-items-center gap-5 text-center">
        <Brand />
        <p className="mono text-[12px] text-muted">404</p>
        <h1 className="page-title">This page is not in the file.</h1>
        <Link to="/" className="btn btn-secondary btn-sm">
          Return to your workspace
        </Link>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />

      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <RegisterPage />
          </PublicOnlyRoute>
        }
      />

      <Route
        path="/overview"
        element={
          <ProtectedRoute role="student">
            <OverviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/applications"
        element={
          <ProtectedRoute role="student">
            <ApplicationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/applications/new"
        element={
          <ProtectedRoute role="student">
            <NewApplicationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/applications/:id"
        element={
          <ProtectedRoute>
            <ApplicationDetailPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin"
        element={
          <ProtectedRoute role="admin">
            <AdminOverviewPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/applications"
        element={
          <ProtectedRoute role="admin">
            <AdminApplicationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/applications/:id"
        element={
          <ProtectedRoute role="admin">
            <ApplicationDetailPage adminView />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/reviews"
        element={
          <ProtectedRoute role="admin">
            <ReviewQueuePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/accuracy"
        element={
          <ProtectedRoute role="admin">
            <AccuracyPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <ProtectedRoute role="admin">
            <AuditPage />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
