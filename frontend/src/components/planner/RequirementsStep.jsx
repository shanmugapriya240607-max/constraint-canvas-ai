import { useEffect } from "react";
import Icon from "../Icon";

export default function RequirementsStep({
  data,
  tasks,
  resources,
  onChange,
  onValidationChange,
}) {
  useEffect(() => {
    const isValid = data.every(
      (r) => r.taskId && r.resourceType && r.quantity > 0
    );
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const uniqueResourceTypes = Array.from(
    new Set(resources.map((r) => r.type))
  );

  const handleAdd = (taskId) => {
    const newReq = {
      id: `temp_req_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      taskId,
      resourceType: uniqueResourceTypes[0] || "",
      quantity: 1,
      specificResourceId: "",
    };
    onChange([...data, newReq]);
  };

  const handleRemove = (id) => {
    onChange(data.filter((r) => r.id !== id));
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((r) => {
        if (r.id === id) {
          const updated = { ...r, [field]: value };
          if (field === "resourceType") {
            updated.specificResourceId = "";
          }
          return updated;
        }
        return r;
      })
    );
  };

  if (tasks.length === 0) {
    return (
      <div className="wizard-step-content">
        <h2>Resource Requirements</h2>
        <div className="empty-state">
          <Icon name="package" size={30} />
          <p>Please add tasks first to define their resource requirements.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step-content">
      <h2>Resource Requirements</h2>
      <p className="helper-text">
        Specify what resources each task needs to be completed.
      </p>

      <div className="list-container">
        {tasks.map((task) => {
          const taskReqs = data.filter((r) => r.taskId === task.id);
          return (
            <div key={task.id} className="resource-group-card">
              <div className="resource-group-header">
                <h4>{task.name}</h4>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => handleAdd(task.id)}
                  title="Add Requirement"
                  disabled={uniqueResourceTypes.length === 0}
                >
                  <Icon name="plus" size={16} />
                </button>
              </div>

              {uniqueResourceTypes.length === 0 && (
                <p className="error-message">
                  No resources defined. Go back and add resources first.
                </p>
              )}

              {taskReqs.length === 0 && uniqueResourceTypes.length > 0 ? (
                <p className="no-data-text">No requirements specified for this task.</p>
              ) : (
                <div className="availability-list">
                  {taskReqs.map((req) => {
                    const compatibleResources = resources.filter(
                      (r) => r.type === req.resourceType
                    );

                    return (
                      <div key={req.id} className="availability-row">
                        <div className="form-group">
                          <label>Type <span className="required">*</span></label>
                          <select
                            value={req.resourceType}
                            onChange={(e) =>
                              handleChange(req.id, "resourceType", e.target.value)
                            }
                          >
                            <option value="">Select Type</option>
                            {uniqueResourceTypes.map((type) => (
                              <option key={type} value={type}>
                                {type}
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="form-group">
                          <label>Quantity <span className="required">*</span></label>
                          <input
                            type="number"
                            min="1"
                            value={req.quantity}
                            onChange={(e) =>
                              handleChange(req.id, "quantity", parseInt(e.target.value) || 1)
                            }
                          />
                        </div>
                        <div className="form-group">
                          <label>Specific Resource (Optional)</label>
                          <select
                            value={req.specificResourceId}
                            onChange={(e) =>
                              handleChange(req.id, "specificResourceId", e.target.value)
                            }
                          >
                            <option value="">Any</option>
                            {compatibleResources.map((res) => (
                              <option key={res.id} value={res.id}>
                                {res.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <button
                          type="button"
                          className="icon-button danger remove-btn"
                          onClick={() => handleRemove(req.id)}
                          title="Remove Requirement"
                        >
                          <Icon name="trash-2" size={16} />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
