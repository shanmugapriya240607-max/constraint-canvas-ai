import { useState, useEffect } from "react";
import Icon from "../Icon";

export default function ConstraintsStep({
  data,
  tasks,
  resources,
  onChange,
  onValidationChange,
}) {
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    const isValid = data.every((c) => {
      const hasType = !!c.type;
      const hasHardness = !!c.hardness;
      const hasValidWeight = c.hardness === "soft" ? parseFloat(c.weight) > 0 : true;
      let validDef = true;
      if (c.type === "deadline") validDef = !!c.definition.task_id && !!c.definition.deadline;
      if (c.type === "dependency")
        validDef = !!c.definition.before_task_id && !!c.definition.after_task_id;
      if (c.type === "preferred_resource")
        validDef = !!c.definition.task_id && !!c.definition.resource_id;

      const requiredFields = {
        resource_capacity: ["resource_id", "capacity"], availability: ["resource_id", "available_from", "available_until"],
        max_work_hours: ["resource_id", "max_hours"], preferred_time: ["task_id", "preferred_before"],
      };
      if (requiredFields[c.type]) validDef = requiredFields[c.type].every(key => c.definition[key] !== undefined && c.definition[key] !== "");
      return hasType && hasHardness && hasValidWeight && validDef;
    });
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const handleAdd = () => {
    const newConstraint = {
      id: `temp_const_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      type: "deadline",
      hardness: "hard",
      weight: 1.0,
      definition: {},
    };
    onChange([...data, newConstraint]);
    setEditingId(newConstraint.id);
  };

  const handleRemove = (id) => {
    onChange(data.filter((c) => c.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((c) => {
        if (c.id === id) {
          if (field === "type") {
            return { ...c, [field]: value, definition: {}, hardness: value.startsWith("preferred_") ? "soft" : "hard" };
          }
          return { ...c, [field]: value };
        }
        return c;
      })
    );
  };

  const handleDefChange = (id, field, value) => {
    onChange(
      data.map((c) => {
        if (c.id === id) {
          return { ...c, definition: { ...c.definition, [field]: value } };
        }
        return c;
      })
    );
  };

  const renderConstraintDefinition = (constraint) => {
    switch (constraint.type) {
      case "deadline":
        return (
          <div className="form-group full">
            <label>Task <span className="required">*</span></label>
            <select
              value={constraint.definition.task_id || ""}
              onChange={(e) => handleDefChange(constraint.id, "task_id", e.target.value)}
            >
              <option value="">Select Task</option>
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
            <label>Deadline <span className="required">*</span>
              <input type="datetime-local" value={constraint.definition.deadline || ""}
                onChange={(e) => handleDefChange(constraint.id, "deadline", e.target.value)} />
            </label>
          </div>
        );
      case "dependency":
        return (
          <div className="form-row">
            <div className="form-group half">
              <label>Before Task <span className="required">*</span></label>
              <select
                value={constraint.definition.before_task_id || ""}
                onChange={(e) => handleDefChange(constraint.id, "before_task_id", e.target.value)}
              >
                <option value="">Select Task</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group half">
              <label>After Task <span className="required">*</span></label>
              <select
                value={constraint.definition.after_task_id || ""}
                onChange={(e) => handleDefChange(constraint.id, "after_task_id", e.target.value)}
              >
                <option value="">Select Task</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
          </div>
        );
      case "preferred_resource":
        return (
          <div className="form-row">
            <div className="form-group half">
              <label>Task <span className="required">*</span></label>
              <select
                value={constraint.definition.task_id || ""}
                onChange={(e) => handleDefChange(constraint.id, "task_id", e.target.value)}
              >
                <option value="">Select Task</option>
                {tasks.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            <div className="form-group half">
              <label>Preferred Resource <span className="required">*</span></label>
              <select
                value={constraint.definition.resource_id || ""}
                onChange={(e) => handleDefChange(constraint.id, "resource_id", e.target.value)}
              >
                <option value="">Select Resource</option>
                {resources.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </div>
          </div>
        );
      case "resource_capacity":
      case "availability":
      case "max_work_hours":
      case "preferred_time": {
        const isTask = constraint.type === "preferred_time";
        const entityField = isTask ? "task_id" : "resource_id";
        const fields = { resource_capacity: ["capacity"], availability: ["available_from", "available_until"],
          max_work_hours: ["max_hours"], preferred_time: ["preferred_before"] }[constraint.type];
        return <div className="form-row">
          <label>{isTask ? "Task" : "Resource"}<select value={constraint.definition[entityField] || ""}
            onChange={e => handleDefChange(constraint.id, entityField, e.target.value)}>
            <option value="">Select {isTask ? "Task" : "Resource"}</option>
            {(isTask ? tasks : resources).map(entity => <option key={entity.id} value={entity.id}>{entity.name}</option>)}
          </select></label>
          {fields.map(field => {
            const numeric = ["capacity", "max_hours"].includes(field);
            return <label key={field}>{field.replaceAll("_", " ")}<input
              type={numeric ? "number" : "datetime-local"} min={field === "capacity" ? 0 : 0.001} step={field === "capacity" ? 1 : "any"}
              value={constraint.definition[field] ?? ""} onChange={e => handleDefChange(constraint.id, field,
                numeric && e.target.value !== "" ? Number(e.target.value) : e.target.value)} /></label>;
          })}
        </div>;
      }
      default:
        return (
          <div className="form-group full">
            <label>Additional Configuration</label>
            <p className="helper-text">This constraint type is supported natively without extra entity mapping.</p>
          </div>
        );
    }
  };

  return (
    <div className="wizard-step-content">
      <h2>Advanced Constraints</h2>
      <p className="helper-text">
        Define specific rules the optimization engine must follow.
      </p>

      {data.length === 0 ? (
        <div className="empty-state small">
          <Icon name="shield" size={24} />
          <p>No extra constraints added.</p>
        </div>
      ) : (
        <div className="list-container">
          {data.map((constraint) => (
            <div key={constraint.id} className="list-item-card">
              {editingId === constraint.id ? (
                <div className="edit-form">
                  <div className="form-row">
                    <div className="form-group half">
                      <label>Type <span className="required">*</span></label>
                      <select
                        value={constraint.type}
                        onChange={(e) => handleChange(constraint.id, "type", e.target.value)}
                      >
                        <option value="deadline">Deadline</option>
                        <option value="dependency">Dependency</option>
                        <option value="resource_capacity">Resource Capacity</option>
                        <option value="availability">Availability</option>
                        <option value="max_work_hours">Max Work Hours</option>
                        <option value="preferred_resource">Preferred Resource</option>
                        <option value="preferred_time">Preferred Time</option>
                      </select>
                    </div>
                    <div className="form-group half">
                      <label>Hardness <span className="required">*</span></label>
                      <select
                        value={constraint.hardness}
                        onChange={(e) => handleChange(constraint.id, "hardness", e.target.value)}
                      >
                        <option value="hard" disabled={constraint.type.startsWith("preferred_")}>Hard (Must be met)</option>
                        <option value="soft" disabled={!constraint.type.startsWith("preferred_")}>Soft (Should be met)</option>
                      </select>
                    </div>
                  </div>

                  {constraint.hardness === "soft" && (
                    <div className="form-row">
                      <div className="form-group full">
                        <label>Weight (1.0 = normal importance)</label>
                        <input
                          type="number"
                          min="0.1"
                          step="0.1"
                          value={constraint.weight}
                          onChange={(e) => handleChange(constraint.id, "weight", e.target.value)}
                        />
                      </div>
                    </div>
                  )}

                  {renderConstraintDefinition(constraint)}

                  <div className="form-actions right">
                    <button
                      type="button"
                      className="button primary small"
                      onClick={() => setEditingId(null)}
                    >
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div className="item-summary">
                  <div className="item-details">
                    <h4>{constraint.type.replace(/_/g, " ")}</h4>
                    <span className={`tag ${constraint.hardness === "hard" ? "danger" : "warning"}`}>
                      {constraint.hardness.toUpperCase()}
                    </span>
                    <span className="detail-text">
                      {constraint.hardness === "soft" && `Weight: ${constraint.weight}`}
                    </span>
                  </div>
                  <div className="item-actions">
                    <button
                      type="button"
                      className="icon-button"
                      onClick={() => setEditingId(constraint.id)}
                      title="Edit Constraint"
                    >
                      <Icon name="edit-2" size={16} />
                    </button>
                    <button
                      type="button"
                      className="icon-button danger"
                      onClick={() => handleRemove(constraint.id)}
                      title="Remove Constraint"
                    >
                      <Icon name="trash-2" size={16} />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <button type="button" className="button secondary add-button" onClick={handleAdd}>
        <Icon name="plus" size={16} /> Add Constraint
      </button>
    </div>
  );
}
