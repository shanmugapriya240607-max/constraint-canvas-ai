import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import SessionGate from "../components/SessionGate";
export default function ProtectedRoute() {
  const { user } = useAuth();
  const location = useLocation();
  return (
    <SessionGate>
      {user ? (
        <Outlet />
      ) : (
        <Navigate
          to="/login"
          replace
          state={{ from: location.pathname + location.search }}
        />
      )}
    </SessionGate>
  );
}
