import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import Icon from "../components/Icon";
import SessionGate from "../components/SessionGate";

export default function AuthLayout({ children }) {
  const { user } = useAuth();
  const { state } = useLocation();
  const from = state?.from;
  const allowed = [
    "/dashboard",
    "/plans",
    "/plans/new",
    "/what-if",
    "/memory",
    "/settings",
  ];
  const destination =
    typeof from === "string" &&
    allowed.includes(from.split("?")[0]) &&
    !from.includes("\\")
      ? from
      : "/dashboard";
  return (
    <SessionGate>
      {user ? (
        <Navigate to={destination} replace />
      ) : (
        <div className="auth-layout">
          <aside className="auth-story">
            <Brand />
            <div className="story-main">
              <span className="eyebrow">
                A little structure. A lot of possibility.
              </span>
              <h1>
                Big ideas.
                <br />
                Clearer plans.
              </h1>
              <p>
                A thoughtful space for your tasks, resources, and the decisions
                that connect them.
              </p>
              <div className="canvas-art" aria-hidden="true">
                <div className="art-line one" />
                <div className="art-line two" />
                <div className="art-node node-one">
                  <span className="node-symbol">
                    <Icon name="layers" />
                  </span>
                  <div>
                    <b>Your idea</b>
                    <small>Start with what matters</small>
                  </div>
                </div>
                <div className="art-node node-two">
                  <span className="node-symbol">
                    <Icon name="branch" />
                  </span>
                  <div>
                    <b>A little clarity</b>
                    <small>Connect the moving parts</small>
                  </div>
                </div>
                <div className="art-node node-three">
                  <span className="node-symbol">
                    <Icon name="check" />
                  </span>
                  <div>
                    <b>A way forward</b>
                    <small>Make room for possibility</small>
                  </div>
                </div>
              </div>
            </div>
            <div className="story-footer">
              <span className="small-dot" /> Your next chapter starts with a
              plan.
            </div>
          </aside>
          <main className="auth-main">
            <div className="mobile-brand">
              <Brand />
            </div>
            {children}
            <p className="auth-footer">
              <Icon name="lock" size={14} /> Your workspace starts with a secure
              sign-in.
            </p>
          </main>
        </div>
      )}
    </SessionGate>
  );
}
