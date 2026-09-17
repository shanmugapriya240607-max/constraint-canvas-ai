import { useState, useMemo } from "react";

export default function GanttChart({ planId, runDetail }) {
  const [selectedTask, setSelectedTask] = useState(null);

  const schedule = useMemo(() => {
    return runDetail?.result?.schedule || [];
  }, [runDetail]);

  const timelineStats = useMemo(() => {
    if (schedule.length === 0) return null;
    
    let minTime = new Date(schedule[0].start_time).getTime();
    let maxTime = new Date(schedule[0].end_time).getTime();

    schedule.forEach(t => {
      const s = new Date(t.start_time).getTime();
      const e = new Date(t.end_time).getTime();
      if (s < minTime) minTime = s;
      if (e > maxTime) maxTime = e;
    });

    const totalDurationMs = maxTime - minTime;
    return { minTime, maxTime, totalDurationMs };
  }, [schedule]);

  if (!schedule || schedule.length === 0) {
    return (
      <div className="gantt-empty">
        <p>No tasks scheduled.</p>
      </div>
    );
  }

  const { minTime, totalDurationMs } = timelineStats;

  // Render hours as timeline markers
  const markers = [];
  if (totalDurationMs > 0) {
    const hours = Math.ceil(totalDurationMs / (1000 * 60 * 60));
    for (let i = 0; i <= hours; i++) {
      const timeMs = minTime + i * 60 * 60 * 1000;
      const pct = (i * 60 * 60 * 1000) / totalDurationMs * 100;
      if (pct <= 100) {
        markers.push({ pct, label: new Date(timeMs).toLocaleTimeString([], { hour: '2-digit' }) });
      }
    }
  }

  const getPriorityClass = (priority) => {
    return `priority-${priority.toLowerCase()}`;
  };

  return (
    <div className="gantt-chart-container">
      <h3>Timeline</h3>
      <div className="gantt-scroll-area">
        <div className="gantt-wrapper">
          <div className="gantt-header">
            <div className="gantt-labels-header">Task</div>
            <div className="gantt-timeline-header">
              {markers.map((m, i) => (
                <div key={i} className="timeline-marker" style={{ left: `${m.pct}%` }}>
                  {m.label}
                </div>
              ))}
            </div>
          </div>

          <div className="gantt-body">
            {schedule.map((task) => {
              const startMs = new Date(task.start_time).getTime();
              const endMs = new Date(task.end_time).getTime();
              const leftPct = totalDurationMs === 0 ? 0 : ((startMs - minTime) / totalDurationMs) * 100;
              const widthPct = totalDurationMs === 0 ? 100 : ((endMs - startMs) / totalDurationMs) * 100;

              const isSelected = selectedTask?.task_id === task.task_id;

              return (
                <div key={task.task_id} className="gantt-row">
                  <div className="gantt-label" title={task.task_name}>
                    {task.task_name}
                  </div>
                  <div className="gantt-track">
                    <div
                      className={`gantt-bar ${getPriorityClass(task.priority)} ${isSelected ? 'selected' : ''}`}
                      style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                      onClick={() => setSelectedTask(task)}
                    >
                      <span className="gantt-bar-label">{task.task_name}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {selectedTask && (
        <div className="task-details-panel">
          <div className="panel-header">
            <h4>Task Details: {selectedTask.task_name}</h4>
            <button className="close-btn" onClick={() => setSelectedTask(null)}>✕</button>
          </div>
          <div className="panel-content">
            <div className="detail-group">
              <span className="detail-label">Start Time:</span>
              <span>{new Date(selectedTask.start_time).toLocaleString()}</span>
            </div>
            <div className="detail-group">
              <span className="detail-label">End Time:</span>
              <span>{new Date(selectedTask.end_time).toLocaleString()}</span>
            </div>
            <div className="detail-group">
              <span className="detail-label">Duration:</span>
              <span>{selectedTask.duration_minutes} min</span>
            </div>
            <div className="detail-group">
              <span className="detail-label">Priority:</span>
              <span className={`badge ${getPriorityClass(selectedTask.priority)}`}>{selectedTask.priority}</span>
            </div>
            <div className="detail-group">
              <span className="detail-label">Assigned Resources:</span>
              <span>
                {selectedTask.assigned_resources && selectedTask.assigned_resources.length > 0 
                  ? selectedTask.assigned_resources.map(r => r.name).join(", ")
                  : "None"}
              </span>
            </div>
            
            <div className="why-schedule-section">
              <h5>Why this schedule?</h5>
              <p className="text-secondary text-sm">
                Based on required resource availability and dependency constraints evaluated during optimization.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
