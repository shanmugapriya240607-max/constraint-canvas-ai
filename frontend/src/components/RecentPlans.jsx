import React, { useState, useEffect } from 'react';
import { getHistory, getHistoryRun } from '../api';

export default function RecentPlans({ onSelectRun, refreshTrigger }) {
  const [historyRuns, setHistoryRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRunId, setSelectedRunId] = useState(null);

  const fetchHistoryList = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getHistory();
      setHistoryRuns(data.runs || []);
    } catch (err) {
      console.error('Failed to load recent plans:', err);
      setError('Could not load recent history runs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistoryList();
  }, [refreshTrigger]);

  const handleSelect = async (runId) => {
    setSelectedRunId(runId);
    try {
      const detailData = await getHistoryRun(runId);
      if (detailData && detailData.result) {
        onSelectRun(detailData.result, detailData.original_text);
      }
    } catch (err) {
      console.error(`Failed to load run ${runId}:`, err);
      alert('Could not retrieve full details for this historical run.');
    }
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '—';
    try {
      const date = new Date(isoStr);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return isoStr;
    }
  };

  return (
    <div className="section-card recent-plans-card">
      <div className="section-card-header">
        <div>
          <h3>Recent Plans (SQLite History)</h3>
          <p className="section-card-desc">
            Browse and reload previously optimized solve runs stored in database
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={fetchHistoryList}
          disabled={loading}
          aria-label="Refresh history list"
        >
          {loading ? 'Refreshing...' : 'Refresh History'}
        </button>
      </div>

      {error ? (
        <div className="history-status-msg text-error">{error}</div>
      ) : historyRuns.length === 0 ? (
        <div className="history-status-msg text-muted">
          No saved solve runs in database yet. Submit a planning requirement above to record history.
        </div>
      ) : (
        <div className="history-grid">
          {historyRuns.map((run) => {
            const isSelected = selectedRunId === run.id;
            let badgeClass = 'status-pill-subtle';
            if (run.status === 'OPTIMAL') badgeClass += ' optimal-badge';
            else if (run.status === 'FEASIBLE') badgeClass += ' feasible-badge';
            else if (run.status === 'NEEDS_INPUT') badgeClass += ' warning-badge';
            else if (run.status === 'INFEASIBLE' || run.status === 'INVALID') badgeClass += ' danger-badge';

            const objectiveText =
              typeof run.objective === 'object' && run.objective !== null
                ? run.objective.type || '—'
                : run.objective || '—';

            return (
              <div
                key={run.id}
                className={`history-item-card ${isSelected ? 'selected-history-card' : ''}`}
                onClick={() => handleSelect(run.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSelect(run.id);
                  }
                }}
                aria-label={`Load run ${run.id}: ${run.problem_title || 'Untitled run'}`}
              >
                <div className="history-card-top">
                  <span className="history-id font-mono">#{run.id}</span>
                  <span className={badgeClass}>{run.status}</span>
                </div>

                <div className="history-card-title">
                  {run.problem_title || 'Untitled Planning Requirement'}
                </div>

                <div className="history-card-details">
                  <span className="history-detail-item font-mono">{objectiveText}</span>
                  <span className="history-detail-item">{run.task_count} tasks</span>
                  <span className="history-detail-item text-muted">{formatDate(run.created_at)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
