import React from 'react';

function parseMin(timeStr) {
  if (!timeStr) return 9999;
  const parts = timeStr.split(':');
  if (parts.length < 2) return 9999;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

export default function TaskTimeline({ tasks = [] }) {
  if (!tasks || tasks.length === 0) {
    return null;
  }

  // Create dependency name lookup map
  const taskNameMap = new Map();
  tasks.forEach((t) => taskNameMap.set(t.id, t.name));

  // Sort tasks by start time, then execution level, then priority score descending
  const sortedTasks = [...tasks].sort((a, b) => {
    const sA = parseMin(a.start);
    const sB = parseMin(b.start);
    if (sA !== sB) return sA - sB;
    const lvlA = a.execution_level || 1;
    const lvlB = b.execution_level || 1;
    if (lvlA !== lvlB) return lvlA - lvlB;
    return (b.priority_score || 0) - (a.priority_score || 0);
  });

  // Group tasks by start time to highlight parallel execution
  const startGroups = new Map();
  sortedTasks.forEach((task) => {
    const sTime = task.start || 'TBD';
    if (!startGroups.has(sTime)) {
      startGroups.set(sTime, []);
    }
    startGroups.get(sTime).push(task);
  });

  return (
    <div className="section-card">
      <div className="section-card-header">
        <div>
          <h3>Task Execution Timeline</h3>
          <p className="section-card-desc">
            Sequential &amp; parallel task execution breakdown by execution level
          </p>
        </div>
      </div>

      <div className="timeline-wrapper">
        <div className="timeline-line"></div>

        {sortedTasks.map((task, idx) => {
          const isParallel =
            task.start && (startGroups.get(task.start) || []).length > 1;

          const depNames = (task.depends_on || []).map(
            (depId) => taskNameMap.get(depId) || depId
          );

          let nodeClass = 'timeline-node-normal';
          if (task.is_critical) nodeClass = 'timeline-node-critical';
          else if (task.is_passive) nodeClass = 'timeline-node-passive';

          return (
            <div key={task.id} className="timeline-item">
              {/* Timeline marker node */}
              <div className={`timeline-node ${nodeClass}`}>
                <span className="node-level font-mono">L{task.execution_level || 1}</span>
              </div>

              {/* Card Content */}
              <div className={`timeline-card ${task.is_critical ? 'card-critical-border' : ''}`}>
                <div className="timeline-card-header">
                  <div className="card-title-group">
                    <span className="task-step-number font-mono">Step {idx + 1}</span>
                    <h4 className="task-card-title">{task.name}</h4>
                    {isParallel && (
                      <span className="badge badge-cyan" title="Executes simultaneously with other tasks">
                        Parallel Execution
                      </span>
                    )}
                  </div>
                  <div className="timeline-time-badge font-mono">
                    {task.start && task.end ? `${task.start} – ${task.end}` : 'Time TBD'}
                    <span className="duration-pill">({task.duration_minutes}m)</span>
                  </div>
                </div>

                <div className="timeline-card-body">
                  <p className="priority-reason-text">
                    <strong>Priority Reason:</strong> {task.priority_reason || 'Standard execution node.'}
                  </p>

                  <div className="timeline-meta-grid">
                    <div className="meta-item">
                      <span className="meta-label">Execution Level:</span>
                      <span className="meta-value font-mono">Level {task.execution_level || 1}</span>
                    </div>

                    <div className="meta-item">
                      <span className="meta-label">Priority Score:</span>
                      <span className="meta-value font-mono">{task.priority_score ?? '—'} / 100</span>
                    </div>

                    <div className="meta-item">
                      <span className="meta-label">Dependencies:</span>
                      <span className="meta-value">
                        {depNames.length > 0 ? depNames.join(', ') : 'None (Root task)'}
                      </span>
                    </div>

                    <div className="meta-item">
                      <span className="meta-label">Required Resources:</span>
                      <span className="meta-value">
                        {task.resources && task.resources.length > 0
                          ? task.resources.join(', ')
                          : 'None'}
                      </span>
                    </div>
                  </div>

                  <div className="timeline-badge-row">
                    {task.is_critical && (
                      <span className="badge badge-amber">Critical Path Node</span>
                    )}
                    {task.is_passive && (
                      <span className="badge badge-cyan">Passive Task</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
