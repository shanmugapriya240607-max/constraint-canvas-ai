export default function InfeasibleView({ issues, recoveryOptions }) {
  return (
    <div className="infeasible-view">
      <div className="infeasible-banner">
        <h2>PLAN INFEASIBLE</h2>
        <p>The solver could not find a valid schedule satisfying all constraints.</p>
      </div>

      {issues && issues.length > 0 && (
        <div className="issues-section">
          <h3>Blocking Issues</h3>
          <ul className="issue-list">
            {issues.map((issue, idx) => (
              <li key={idx} className="issue-card">
                <div className="issue-header">
                  <span className={`issue-severity severity-${issue.severity}`}>{issue.severity}</span>
                  <strong>{issue.type}</strong>
                </div>
                <p className="issue-message">{issue.message}</p>
                {(issue.required !== null || issue.available !== null) && (
                  <div className="issue-details">
                    {issue.required !== null && <span>Required: {issue.required}</span>}
                    {issue.available !== null && <span>Available: {issue.available}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {recoveryOptions && recoveryOptions.length > 0 && (
        <div className="recovery-section">
          <h3>Recovery Options</h3>
          <div className="recovery-grid">
            {recoveryOptions.map((opt, idx) => (
              <div key={idx} className="recovery-card">
                <h4>{opt.title}</h4>
                <p>{opt.explanation}</p>
                {opt.changes_required && (
                  <div className="recovery-changes">
                    <strong>Required Change:</strong> {opt.changes_required}
                  </div>
                )}
                {opt.affected_entities && (
                  <div className="recovery-affected">
                    <strong>Affected:</strong> {opt.affected_entities.join(", ")}
                  </div>
                )}
                <div className="recovery-action">
                  <button className="btn secondary" disabled>Review Fix</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
