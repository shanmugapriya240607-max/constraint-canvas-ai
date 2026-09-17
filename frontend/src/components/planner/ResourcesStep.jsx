import { useState, useEffect } from "react";
import Icon from "../Icon";

export default function ResourcesStep({ data, onChange, onValidationChange }) {
  const [editingId, setEditingId] = useState(null);

  useEffect(() => {
    // Basic validation: at least 1 valid resource? The prompt doesn't strictly say it's required to have one,
    // but typically a plan needs at least one resource. For now, we just validate the individual items.
    const isValid = data.every(
      (r) => r.name.trim() && r.type.trim() && r.capacity > 0
    );
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const handleAdd = () => {
    const newResource = {
      id: `temp_res_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      name: "",
      type: "developer",
      capacity: 1,
      cost: "",
      active: true,
    };
    onChange([...data, newResource]);
    setEditingId(newResource.id);
  };

  const handleRemove = (id) => {
    onChange(data.filter((r) => r.id !== id));
    if (editingId === id) setEditingId(null);
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((r) => (r.id === id ? { ...r, [field]: value } : r))
    );
  };

  return (
    <div className="wizard-step-content">
      <h2>Resources</h2>
      <p className="helper-text">
        Add the resources (people, machines, rooms) available for your plan.
      </p>

      {data.length === 0 ? (
        <div className="empty-state small">
          <Icon name="users" size={24} />
          <p>No resources added yet.</p>
        </div>
      ) : (
        <div className="list-container">
          {data.map((resource) => (
            <div key={resource.id} className="list-item-card">
              {editingId === resource.id ? (
                <div className="edit-form">
                  <div className="form-row">
                    <div className="form-group half">
                      <label>Name <span className="required">*</span></label>
                      <input
                        type="text"
                        value={resource.name}
                        onChange={(e) => handleChange(resource.id, "name", e.target.value)}
                        placeholder="e.g. John Doe, Room 101"
                      />
                    </div>
                    <div className="form-group half">
                      <label>Type <span className="required">*</span></label>
                      <input
                        type="text"
                        value={resource.type}
                        onChange={(e) => handleChange(resource.id, "type", e.target.value)}
                        placeholder="e.g. developer, machine"
                      />
                    </div>
                  </div>
                  <div className="form-row">
                    <div className="form-group third">
                      <label>Capacity <span className="required">*</span></label>
                      <input
                        type="number"
                        min="1"
                        value={resource.capacity}
                        onChange={(e) => handleChange(resource.id, "capacity", parseInt(e.target.value) || 1)}
                      />
                    </div>
                    <div className="form-group third">
                      <label>Cost/hr</label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={resource.cost}
                        onChange={(e) => handleChange(resource.id, "cost", e.target.value)}
                        placeholder="Optional"
                      />
                    </div>
                    <div className="form-group third checkbox-group">
                      <label>
                        <input
                          type="checkbox"
                          checked={resource.active}
                          onChange={(e) => handleChange(resource.id, "active", e.target.checked)}
                        />
                        Active
                      </label>
                    </div>
                  </div>
                  <div className="form-actions right">
                    <button
                      type="button"
                      className="button primary small"
                      onClick={() => setEditingId(null)}
                      disabled={!resource.name.trim() || !resource.type.trim() || resource.capacity <= 0}
                    >
                      Done
                    </button>
                  </div>
                </div>
              ) : (
                <div className="item-summary">
                  <div className="item-details">
                    <h4>{resource.name}</h4>
                    <span className="tag neutral">{resource.type}</span>
                    <span className="detail-text">
                      Capacity: {resource.capacity}
                      {resource.cost ? ` | $${resource.cost}/hr` : ""}
                      {resource.active ? "" : " (Inactive)"}
                    </span>
                  </div>
                  <div className="item-actions">
                    <button
                      type="button"
                      className="icon-button"
                      onClick={() => setEditingId(resource.id)}
                      title="Edit Resource"
                    >
                      <Icon name="edit-2" size={16} />
                    </button>
                    <button
                      type="button"
                      className="icon-button danger"
                      onClick={() => handleRemove(resource.id)}
                      title="Remove Resource"
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
        <Icon name="plus" size={16} /> Add Resource
      </button>
    </div>
  );
}
