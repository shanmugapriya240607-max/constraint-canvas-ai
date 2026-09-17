import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Placeholder from "./pages/Placeholder";
import CreatePlan from "./pages/CreatePlan";
import ProtectedRoute from "./routes/ProtectedRoute";
import AppLayout from "./layouts/AppLayout";

export default function App() {
  const { pathname } = useLocation();
  useEffect(() => {
    const titles = {
      "/login": "Sign in",
      "/register": "Create account",
      "/dashboard": "Dashboard",
      "/plans/new": "New Plan",
      "/plans": "Planning History",
      "/settings": "Settings",
      "/memory": "Memory",
      "/what-if": "What-If Simulator",
    };
    document.title =
      (titles[pathname] || "Workspace") + " | ConstraintCanvas AI";
  }, [pathname]);
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route
            path="/plans/new"
            element={<CreatePlan />}
          />
          <Route
            path="/plans"
            element={<Placeholder title="Planning History" icon="history" />}
          />
          <Route
            path="/what-if"
            element={<Placeholder title="What-If Simulator" icon="branch" />}
          />
          <Route
            path="/memory"
            element={<Placeholder title="Memory" icon="memory" />}
          />
          <Route
            path="/settings"
            element={<Placeholder title="Settings" icon="settings" />}
          />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
