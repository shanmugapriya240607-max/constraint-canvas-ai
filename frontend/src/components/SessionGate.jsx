import { useAuth } from "../context/AuthContext";
import Brand from "./Brand";
export default function SessionGate({ children }) {
  const { status, error, retry, logout } = useAuth();
  if (status === "loading")
    return (
      <div className="session-screen">
        <Brand />
        <p role="status">Checking your session…</p>
        <span className="spinner" />
      </div>
    );
  if (status === "error")
    return (
      <div className="session-screen">
        <Brand />
        <h1>Let’s reconnect</h1>
        <p role="alert">{error}</p>
        <div className="button-row">
          <button className="button primary" onClick={retry}>
            Try again
          </button>
          <button className="button secondary" onClick={logout}>
            Back to login
          </button>
        </div>
      </div>
    );
  return children;
}
