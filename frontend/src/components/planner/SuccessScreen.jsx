import { Link } from "react-router-dom";
import Icon from "../Icon";

export default function SuccessScreen({ planId, counts }) {
  return (
    <div className="wizard-step-content success-screen">
      <div className="success-icon-container">
        <Icon name="check-circle" size={64} className="success-icon" />
      </div>
      
      <h2>Plan Created Successfully!</h2>
      <p className="helper-text">
        Your planning problem and all related entities have been saved to the database.
      </p>

      <div className="success-summary">
        <div className="summary-stat">
          <span className="stat-value">{counts.tasks}</span>
          <span className="stat-label">Tasks</span>
        </div>
        <div className="summary-stat">
          <span className="stat-value">{counts.resources}</span>
          <span className="stat-label">Resources</span>
        </div>
        <div className="summary-stat">
          <span className="stat-value">{counts.dependencies}</span>
          <span className="stat-label">Dependencies</span>
        </div>
        <div className="summary-stat">
          <span className="stat-value">{counts.constraints}</span>
          <span className="stat-label">Constraints</span>
        </div>
      </div>

      <div className="success-actions">
        {/* Navigates to a placeholder result route for now */}
        <Link to={`/plans/${planId}/results`} className="button primary large">
          <Icon name="zap" size={18} /> Optimize Plan
        </Link>
        <Link to="/plans" className="button secondary large">
          <Icon name="list" size={18} /> View All Plans
        </Link>
      </div>
    </div>
  );
}
