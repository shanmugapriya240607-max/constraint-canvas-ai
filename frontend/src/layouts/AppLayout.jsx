import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Brand from "../components/Brand";
import Icon from "../components/Icon";

const navigation = [
  ["/dashboard", "Dashboard", "grid"],
  ["/plans/new", "New Plan", "plus"],
  ["/plans", "Planning History", "history"],
  ["/what-if", "What-If Simulator", "branch"],
  ["/memory", "Memory", "memory"],
  ["/settings", "Settings", "settings"],
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const title =
    navigation.find(([path]) => path === location.pathname)?.[1] || "Workspace";
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <Brand />
        <span className="sidebar-label">WORKSPACE</span>
        <button
          className="mobile-menu button secondary"
          onClick={() => setOpen(!open)}
          aria-expanded={open}
          aria-controls="workspace-nav"
        >
          <Icon name={open ? "close" : "menu"} /> Menu
        </button>
        <nav
          id="workspace-nav"
          aria-label="Workspace"
          className={open ? "is-open" : ""}
        >
          {navigation.map(([path, label, icon]) => (
            <NavLink end key={path} to={path} onClick={() => setOpen(false)}>
              <Icon name={icon} />
              <span>{label}</span>
              {path === "/dashboard" && <span className="nav-dot" />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="tag">EARLY PREVIEW</span>
          <p>A space for better plans.</p>
          <small>
            Your workspace is taking shape.
            <br />
            More tools are on the way.
          </small>
        </div>
        <div className="sidebar-bottom">
          <span className="small-dot" /> ConstraintCanvas AI
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            ConstraintCanvas AI <span>/</span>
            <strong>{title}</strong>
          </div>
          <div className="user-controls">
            <span className="avatar" aria-hidden="true">
              {user.name.slice(0, 1).toUpperCase()}
            </span>
            <span className="user-name">{user.name}</span>
            <button onClick={logout} className="logout" aria-label="Log out">
              <Icon name="logout" />
              <span>Log out</span>
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content">
          <Outlet />
        </main>
        <footer className="workspace-footer">
          <span>ConstraintCanvas AI</span>
          <span>Room to think. Space to plan.</span>
        </footer>
      </div>
    </div>
  );
}
