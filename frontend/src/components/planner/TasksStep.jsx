import { useState, useEffect } from "react";
import Icon from "../Icon";

export default function TasksStep({ data, onChange, onValidationChange }) {
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    const isValid = data.every(
      (t) => {
        const hasName = t.name.trim();
        const hasDuration = t.durationValue > 0 && t.durationUnit;
        let validDates = true;
        if (t.earliestStart && t.deadline) {
          validDates = new Date(t.deadline) > new Date(t.earliestStart);
        }
        return hasName && hasDuration && validDates;
      }
    );
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const handleAdd = () => {
    const newTask = {
      id: `temp_task_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      name: "",
      description: "",
      durationValue: 1,
      durationUnit: "hours",
      priority: "medium",
      earliestStart: "",
      deadline: "",
    };
    onChange([...data, newTask]);
    setEditingId(newTask.id);
  };

  const handleRemove = (id) => {
    onChange(data.filter((t) => t.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((t) => (t.id === id ? { ...t, [field]: value } : t))
    );
  };

  return (
    <div className="wizard-step-content">
      <h2>Tasks</h2>
      <p className="helper-text">
        Define the jobs or activities that need to be scheduled.
      </p>

      {data.length === 0 ? (
        <div className="empty-state small">
          <Icon name="check-square" size={24} />
          <p>No tasks added yet.</p>
        </div>
      ) : (
        <div className="list-container">
          {data.map((task) => {
            let dateError = false;
            if (task.earliestStart && task.deadline) {
              dateError = new Date(task.deadline) <= new Date(task.earliestStart);
            }

            return (
              <div key={task.id} className="list-item-card">
                {editingId === task.id ? (
                  <div className="edit-form">
                    <div className="form-row">
                      <div className="form-group full">
                        <label>Name <span className="required">*</span></label>
                        <input
                          type="text"
                          value={task.name}
                          onChange={(e) => handleChange(task.id, "name", e.target.value)}
                          placeholder="e.g. Develop Backend API"
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group full">
                        <label>Description</label>
                        <textarea
                          rows="2"
                          value={task.description}
                          onChange={(e) => handleChange(task.id, "description", e.target.value)}
                          placeholder="Optional details"
                        />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group third">
                        <label>Duration <span className="required">*</span></label>
                        <div className="input-group">
                          <input
                            type="number"
                            min="0.1"
                            step="0.1"
                            value={task.durationValue}
                            onChange={(e) => handleChange(task.id, "durationValue", e.target.value)}
                          />
                          <select
                            value={task.durationUnit}
                            onChange={(e) => handleChange(task.id, "durationUnit", e.target.value)}
                          >
                            <option value="seconds">secs</option>
                            <option value="minutes">mins</option>
                            <option value="hours">hours</option>
                          </select>
                        </div>
                      </div>
                      <div className="form-group third">
                        <label>Priority</label>
                        <select
                          value={task.priority}
                          onChange={(e) => handleChange(task.id, "priority", e.target.value)}
                        >
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="high">High</option>
                          <option value="critical">Critical</option>
                        </select>
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group half">
                        <label>Earliest Start</label>
                        <input
                          type="datetime-local"
                          value={task.earliestStart}
                          onChange={(e) => handleChange(task.id, "earliestStart", e.target.value)}
                          className={dateError ? "error" : ""}
                        />
                      </div>
                      <div className="form-group half">
                        <label>Deadline</label>
                        <input
                          type="datetime-local"
                          value={task.deadline}
                          onChange={(e) => handleChange(task.id, "deadline", e.target.value)}
                          className={dateError ? "error" : ""}
                        />
                      </div>
                    </div>
                    {dateError && (
                      <div className="error-message">Deadline must be after Earliest Start</div>
                    )}
                    <div className="form-actions right">
                      <button
                        type="button"
                        className="button primary small"
                        onClick={() => setEditingId(null)}
                        disabled={!task.name.trim() || task.durationValue <= 0 || dateError}
                      >
                        Done
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="item-summary">
                    <div className="item-details">
                      <h4>{task.name}</h4>
                      <span className={`tag priority-${task.priority}`}>{task.priority}</span>
                      <span className="detail-text">
                        Duration: {task.durationValue} {task.durationUnit}
                        {task.deadline && ` | Due: ${new Date(task.deadline).toLocaleString()}`}
                      </span>
                    </div>
                    <div className="item-actions">
                      <button
                        type="button"
                        className="icon-button"
                        onClick={() => setEditingId(task.id)}
                        title="Edit Task"
                      >
                        <Icon name="edit-2" size={16} />
                      </button>
                      <button
                        type="button"
                        className="icon-button danger"
                        onClick={() => handleRemove(task.id)}
                        title="Remove Task"
                      >
                        <Icon name="trash-2" size={16} />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <button type="button" className="button secondary add-button" onClick={handleAdd}>
        <Icon name="plus" size={16} /> Add Task
      </button>
    </div>
  );
}
