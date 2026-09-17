export default function RisksAndBottlenecks({ risks, bottlenecks }) {
  const hasRisks = risks && risks.length > 0;
  const hasBottlenecks = bottlenecks && bottlenecks.length > 0;

  if (!hasRisks && !hasBottlenecks) {
    return (
      <div className="card risks-card empty">
        <h3>Risks & Bottlenecks</h3>
        <p className="text-secondary">No significant planning risks detected.</p>
      </div>
    );
  }

  return (
    <div className="risks-bottlenecks-container">
      {hasRisks && (
        <div className="card risks-card">
          <h3>Risks</h3>
          <ul className="risk-list">
            {risks.map((risk, idx) => (
              <li key={idx} className="risk-item">
                <span className="risk-icon">⚠</span>
                <div className="risk-content">
                  <p>{risk.message}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasBottlenecks && (
        <div className="card bottlenecks-card">
          <h3>Bottlenecks</h3>
          <ul className="bottleneck-list">
            {bottlenecks.map((bn, idx) => (
              <li key={idx} className="bottleneck-item">
                <h4>{bn.type === 'resource' ? 'Resource Bottleneck' : 'Dependency Bottleneck'}</h4>
                {bn.name && <div className="bottleneck-name">{bn.name}</div>}
                {bn.utilization_percent && (
                  <div className="bottleneck-util">Utilization: {bn.utilization_percent.toFixed(1)}%</div>
                )}
                <p className="bottleneck-reason text-secondary">{bn.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
