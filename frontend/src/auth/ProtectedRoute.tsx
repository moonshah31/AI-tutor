import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  if (loading) return <main className="page-shell"><p>Checking your session…</p></main>;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
