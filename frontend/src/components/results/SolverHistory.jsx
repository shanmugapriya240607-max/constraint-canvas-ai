export default function SolverHistory({ runs }) {
  if (!runs || runs.length === 0) return null;

  return (
    <div className="card solver-history-card">
      <h3>Recent Solver Runs</h3>
      <div className="history-table-container">
        <table className="history-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Status</th>
              <th>Makespan</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {runs.slice(0, 5).map((run) => (
              <tr key={run.id || run.run_id} className={run.status.toLowerCase()}>
                <td>
                  {new Date(run.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </td>
                <td>
                  <span className={`status-badge-small ${run.status.toLowerCase()}`}>
                    {run.status}
                  </span>
                </td>
                <td>
                  {run.makespan
                    ? new Date(run.makespan).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "-"}
                </td>
                <td>
                  {run.solve_duration_ms
                    ? `${(run.solve_duration_ms / 1000).toFixed(2)}s`
                    : "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
