export default function StatusHeader({ status, health, solverRuns }) {
  const latestRun = solverRuns && solverRuns.length > 0 ? solverRuns[0] : null;

  return (
    <div className={`status-header ${status.toLowerCase()}`}>
      <div className="status-badge">
        <h2>{status} PLAN</h2>
      </div>
      
      <div className="status-metrics">
        <div className="metric">
          <span className="label">Health</span>
          <span className="value">
            {health ? `${health.score} / 100` : "N/A"}
          </span>
        </div>
        
        {latestRun && (
          <>
            <div className="metric">
              <span className="label">Completion Time</span>
              <span className="value">
                {latestRun.makespan 
                  ? new Date(latestRun.makespan).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
                  : "N/A"}
              </span>
            </div>
            <div className="metric">
              <span className="label">Solver Time</span>
              <span className="value">
                {latestRun.solve_duration_ms ? `${(latestRun.solve_duration_ms / 1000).toFixed(2)}s` : "N/A"}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
