import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Icon from "../components/Icon";

const metrics = [
  ["Total Plans", "layers", "Your plans, in one place", "totalPlans"],
  ["Resources", "grid", "The people and tools behind them", "resources"],
  ["Active Risks", "alert", "What needs your attention", "activeRisks"],
  ["Plan Health", "pulse", "A clearer picture of progress", "planHealth"],
];

// Values remain unknown until a later block connects real planning data.
export default function Dashboard({ summary = null, loading = false }) {
  const { user } = useAuth();
  const firstName = user.name.trim().split(/\s+/)[0];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR WORKSPACE, AT A GLANCE</span>
          <h1>Welcome, {firstName}.</h1>
          <p>Here’s where your next great plan begins.</p>
        </div>
        <Link className="button primary" to="/plans/new">
          <Icon name="plus" size={18} />
          Create New Plan
        </Link>
      </div>
      <section className="welcome-panel">
        <div>
          <span className="tag">A FRESH CANVAS</span>
          <h2>Make room for what’s next.</h2>
          <p>
            Bring your ideas, tasks, and resources together.
            <br />
            Your planning workspace is ready to take shape.
          </p>
          <Link to="/plans/new" className="text-link">
            Explore your workspace <Icon name="arrow" size={17} />
          </Link>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <div className="art-square square-back" />
          <div className="art-square square-front">
            <Icon name="layers" size={64} />
          </div>
          <span className="art-spark">+</span>
        </div>
      </section>
      <section
        className="metrics"
        aria-label="Workspace overview"
        aria-busy={loading}
      >
        {metrics.map(([label, icon, description, key]) => (
          <article className="metric-card" key={key}>
            <div className="metric-title">
              <h2>{label}</h2>
              <span className={"metric-icon " + icon}>
                <Icon name={icon} />
              </span>
            </div>
            <strong className="metric-value">
              {loading ? (
                <span className="skeleton" aria-label="Loading" />
              ) : (
                (summary?.[key] ?? "—")
              )}
            </strong>
            <span className="metric-description">{description}</span>
            <div className="metric-status">
              {loading
                ? "Loading…"
                : summary?.[key] == null
                  ? "Not connected yet"
                  : "Workspace data"}
            </div>
          </article>
        ))}
      </section>
      <section className="recent-panel">
        <header>
          <div>
            <h2>Recent Plans</h2>
            <p>Your latest work will find a home here.</p>
          </div>
          <span className="tag neutral">WORKSPACE PREVIEW</span>
        </header>
        <div className="empty-state">
          <div className="empty-icon">
            <Icon name="layers" size={30} />
          </div>
          <h3>A blank canvas, full of possibility.</h3>
          <p>
            Plans aren’t connected to this view yet.
            <br />
            Your saved plans will appear here when planning is available.
          </p>
          <Link to="/plans/new" className="button secondary">
            <Icon name="plus" size={17} />
            Create New Plan
          </Link>
        </div>
      </section>
      <p className="dashboard-note">
        <Icon name="lock" size={15} /> Signed in to your personal workspace.
      </p>
    </>
  );
}
