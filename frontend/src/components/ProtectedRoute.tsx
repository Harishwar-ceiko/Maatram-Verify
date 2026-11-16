import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, landingFor } from "../lib/auth";
import { Brand, Spinner } from "./ui";

export function ProtectedRoute({
  children,
  role,
}: {
  children: ReactNode;
  role?: "student" | "admin";
}) {
  const { user, state } = useAuth();
  const location = useLocation();

  if (state === "loading") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <div className="grid justify-items-center gap-5">
          <Brand />
          <Spinner label="Checking your session" />
        </div>
      </div>
    );
  }

  if (state === "anonymous" || !user) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  if (role && user.role !== role) {
    return <Navigate to={landingFor(user.role)} replace />;
  }

  return <>{children}</>;
}

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { user, state } = useAuth();
  if (state === "loading") {
    return (
      <div className="grid min-h-dvh place-items-center">
        <Spinner label="Loading" />
      </div>
    );
  }
  if (state === "authenticated" && user) {
    return <Navigate to={landingFor(user.role)} replace />;
  }
  return <>{children}</>;
}
