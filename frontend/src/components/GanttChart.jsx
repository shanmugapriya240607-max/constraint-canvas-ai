import React from 'react';

function hhmmToMin(timeStr) {
  if (!timeStr) return 0;
  const parts = timeStr.split(':');
  if (parts.length < 2) return 0;
  return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
}

function minToHhmm(minutes) {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

export default function GanttChart({ tasks = [] }) {
  if (!tasks || tasks.length === 0) {
    return null;
  }

  // Filter tasks that have scheduled timings
  const scheduledTasks = tasks.filter((t) => t.start && t.end);
  if (scheduledTasks.length === 0) {
    return null;
  }

  // 1. Calculate bounding timeline range
  let minStart = Infinity;
  let maxEnd = -Infinity;

  scheduledTasks.forEach((t) => {
    const sMin = hhmmToMin(t.start);
    const eMin = hhmmToMin(t.end);
    if (sMin < minStart) minStart = sMin;
    if (eMin > maxEnd) maxEnd = eMin;
  });

  if (minStart === Infinity) minStart = 0;
  if (maxEnd === -Infinity || maxEnd <= minStart) maxEnd = minStart + 60;

  const totalDuration = maxEnd - minStart || 60;

  // Generate 5 to 7 time axis tick marks
  const tickCount = 6;
  const timeTicks = [];
  for (let i = 0; i <= tickCount; i++) {
    const tickMin = Math.round(minStart + (i * totalDuration) / tickCount);
    timeTicks.push({
      minute: tickMin,
      label: minToHhmm(tickMin),
      percent: (i / tickCount) * 100,
    });
  }

  return (
    <div className="section-card">
      <div className="section-card-header">
        <div>
          <h3>Dynamic Gantt Chart</h3>
          <p className="section-card-desc">
            Visual schedule timeline from {minToHhmm(minStart)} to {minToHhmm(maxEnd)} ({totalDuration} mins)
          </p>
        </div>
        <div className="gantt-legend">
          <div className="legend-item">
            <span className="legend-box normal-bg"></span>
            <span>Normal Task</span>
          </div>
          <div className="legend-item">
            <span className="legend-box passive-bg"></span>
            <span>Passive / Background</span>
          </div>
          <div className="legend-item">
            <span className="legend-box critical-bg"></span>
            <span>Critical Path</span>
          </div>
        </div>
      </div>

      <div className="gantt-container-scroll">
        <div className="gantt-chart-inner">
          {/* Time Axis Header */}
          <div className="gantt-axis-row">
            <div className="gantt-label-column">Task</div>
            <div className="gantt-timeline-column">
              <div className="gantt-axis-ticks">
                {timeTicks.map((tick) => (
                  <div
                    key={tick.minute}
                    className="gantt-tick"
                    style={{ left: `${tick.percent}%` }}
                  >
                    <span>{tick.label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Task Rows */}
          <div className="gantt-rows">
            {scheduledTasks.map((task) => {
              const startMin = hhmmToMin(task.start);
              const endMin = hhmmToMin(task.end);
              const duration = Math.max(1, endMin - startMin);

              const leftPercent = Math.max(
                0,
                Math.min(100, ((startMin - minStart) / totalDuration) * 100)
              );
              const widthPercent = Math.max(
                1,
                Math.min(100 - leftPercent, (duration / totalDuration) * 100)
              );

              let barClass = 'gantt-bar-normal';
              if (task.is_critical) {
                barClass = 'gantt-bar-critical';
              } else if (task.is_passive) {
                barClass = 'gantt-bar-passive';
              }

              const tooltipText = `${task.name}\nTiming: ${task.start} – ${task.end} (${task.duration_minutes}m)\nExecution Level: ${task.execution_level || 1}\nPriority Score: ${task.priority_score || '—'}\n${task.priority_reason || ''}`;

              return (
                <div key={task.id} className="gantt-row">
                  <div className="gantt-label-column" title={task.name}>
                    <span className="gantt-task-name">{task.name}</span>
                    <span className="gantt-task-meta">({task.duration_minutes}m)</span>
                  </div>

                  <div className="gantt-timeline-column">
                    {/* Vertical grid lines corresponding to ticks */}
                    {timeTicks.map((tick) => (
                      <div
                        key={`line-${tick.minute}`}
                        className="gantt-grid-line"
                        style={{ left: `${tick.percent}%` }}
                      ></div>
                    ))}

                    {/* Schedule Bar */}
                    <div
                      className={`gantt-bar ${barClass}`}
                      style={{
                        left: `${leftPercent}%`,
                        width: `${widthPercent}%`,
                      }}
                      title={tooltipText}
                      aria-label={`${task.name} from ${task.start} to ${task.end}`}
                    >
                      <span className="gantt-bar-label">
                        {task.start}–{task.end}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
