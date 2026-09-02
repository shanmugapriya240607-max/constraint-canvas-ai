import React from 'react';

export default function ExtractedData({ result }) {
  if (!result || (result.status !== 'OPTIMAL' && result.status !== 'FEASIBLE')) {
    return null;
  }

  const tasks = result.tasks || [];
  const confidence =
    typeof result.extraction_confidence === 'number'
      ? `${Math.round(result.extraction_confidence * 100)}%`
      : '—';

  const objectiveType =
    typeof result.objective === 'object' && result.objective !== null
      ? result.objective.type || '—'
      : result.objective || '—';

  const criticalCount = tasks.filter((t) => t.is_critical).length;

  const isOffline = result.parser_mode === 'OFFLINE_RULES';

  // Find overall start and end
  let overallStart = '—';
  let overallEnd = '—';
  if (tasks.length > 0) {
    const validStarts = tasks.filter((t) => t.start).map((t) => t.start);
    const validEnds = tasks.filter((t) => t.end).map((t) => t.end);
    if (validStarts.length > 0) validStarts.sort();
    if (validEnds.length > 0) validEnds.sort();
    if (validStarts.length > 0) overallStart = validStarts[0];
    if (validEnds.length > 0) overallEnd = validEnds[validEnds.length - 1];
  }

  return (
    <div className="summary-card">
      <div className="summary-header">
        <div>
          <span className="summary-subtitle">PLANNING METRICS</span>
          <h2 className="summary-title">{result.problem_title || 'Planning Schedule'}</h2>
        </div>
        <div className="summary-badges">
          <span className={`status-pill ${result.status.toLowerCase()}`}>
            {result.status === 'OPTIMAL' ? 'Optimal Solution' : 'Feasible Solution'}
          </span>
          <span className="status-pill mode-badge">
            {isOffline ? 'Parser: Offline Rules' : 'Parser: OpenAI'}
          </span>
        </div>
      </div>

      {isOffline && (
        <div className="offline-demo-banner">
          <span className="offline-icon">⚡</span>
          <span>Offline demo mode active — deterministic natural-language parsing</span>
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Objective</span>
          <span className="metric-value code-font">{objectiveType}</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Confidence</span>
          <span className="metric-value highlight-cyan">{confidence}</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Total Tasks</span>
          <span className="metric-value">{tasks.length}</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Makespan</span>
          <span className="metric-value">{result.makespan_minutes ?? '—'} mins</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Schedule Window</span>
          <span className="metric-value highlight-violet">
            {overallStart} – {overallEnd}
          </span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Critical Tasks</span>
          <span className="metric-value highlight-amber">{criticalCount}</span>
        </div>
      </div>
    </div>
  );
}
