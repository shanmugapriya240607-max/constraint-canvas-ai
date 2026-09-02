import React from 'react';

export default function ResultTable({ tasks = [] }) {
  if (!tasks || tasks.length === 0) {
    return null;
  }

  // Create a map for resolving dependency IDs to Task Names
  const taskNameMap = new Map();
  tasks.forEach((t) => {
    taskNameMap.set(t.id, t.name);
  });

  // Helper to convert HH:MM to minutes for sorting without mutating original array
  const parseMin = (timeStr) => {
    if (!timeStr) return 9999;
    const parts = timeStr.split(':');
    if (parts.length < 2) return 9999;
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  };

  const sortedTasks = [...tasks].sort((a, b) => {
    const startA = parseMin(a.start);
    const startB = parseMin(b.start);
    if (startA !== startB) return startA - startB;
    return (a.execution_level || 1) - (b.execution_level || 1);
  });

  return (
    <div className="section-card">
      <div className="section-card-header">
        <h3>Optimized Task Schedule Table</h3>
        <span className="section-card-count">{sortedTasks.length} tasks scheduled</span>
      </div>

      <div className="table-responsive">
        <table className="schedule-table">
          <thead>
            <tr>
              <th scope="col">Order</th>
              <th scope="col">Priority</th>
              <th scope="col">Task Name</th>
              <th scope="col">Duration</th>
              <th scope="col">Start</th>
              <th scope="col">End</th>
              <th scope="col">Dependencies</th>
              <th scope="col">Resources</th>
              <th scope="col">Reason</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {sortedTasks.map((task, index) => {
              const depNames = (task.depends_on || []).map(
                (depId) => taskNameMap.get(depId) || depId
              );

              return (
                <tr key={task.id} className={task.is_critical ? 'row-critical' : ''}>
                  <td className="text-center font-mono">{index + 1}</td>
                  <td>
                    <div className="priority-badge">
                      <span className="score-val">{task.priority_score ?? '—'}</span>
                      <span className="level-val">L{task.execution_level ?? 1}</span>
                    </div>
                  </td>
                  <td className="font-semibold">{task.name}</td>
                  <td>{task.duration_minutes ? `${task.duration_minutes}m` : '—'}</td>
                  <td className="font-mono highlight-violet">{task.start || '—'}</td>
                  <td className="font-mono highlight-violet">{task.end || '—'}</td>
                  <td className="text-muted">
                    {depNames.length > 0 ? (
                      <div className="dep-tags">
                        {depNames.map((name) => (
                          <span key={name} className="dep-tag">
                            {name}
                          </span>
                        ))}
                      </div>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="text-muted">
                    {task.resources && task.resources.length > 0
                      ? task.resources.join(', ')
                      : '—'}
                  </td>
                  <td className="text-secondary small-text">
                    {task.priority_reason || '—'}
                  </td>
                  <td>
                    <div className="badge-group">
                      {task.is_critical && (
                        <span className="badge badge-amber" title="Belongs to critical path">
                          Critical
                        </span>
                      )}
                      {task.is_passive && (
                        <span className="badge badge-cyan" title="Passive background activity">
                          Passive
                        </span>
                      )}
                      {!task.is_critical && !task.is_passive && (
                        <span className="badge badge-default">Normal</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
