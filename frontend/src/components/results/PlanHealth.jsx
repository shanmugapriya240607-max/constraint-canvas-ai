export default function PlanHealth({ health }) {
  if (!health) return null;

  return (
    <div className="card plan-health-card">
      <div className="card-header">
        <h3>Plan Health</h3>
        <div className={`health-grade grade-${health.grade.toLowerCase()}`}>
          {health.grade.toUpperCase()}
        </div>
      </div>
      
      <div className="health-score-display">
        <span className="score-number">{health.score}</span>
        <span className="score-total">/ 100</span>
      </div>
      
      {health.factors && health.factors.length > 0 && (
        <div className="health-factors">
          <h4>Factors</h4>
          <ul>
            {health.factors.map((factor, index) => (
              <li key={index} className="factor-item">
                <div className="factor-header">
                  <span className="factor-name">{factor.name}</span>
                  <span className={`factor-impact ${factor.impact < 0 ? 'negative' : 'positive'}`}>
                    {factor.impact > 0 ? '+' : ''}{factor.impact}
                  </span>
                </div>
                <p className="factor-reason text-secondary">{factor.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      <p className="health-disclaimer text-secondary text-sm">
        * Health score is calculated based on deterministic planning metrics such as slack and utilization.
      </p>
    </div>
  );
}
