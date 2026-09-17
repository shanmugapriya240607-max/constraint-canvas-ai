import { useEffect } from "react";
import Icon from "../Icon";

export default function AvailabilityStep({
  data,
  resources,
  onChange,
  onValidationChange,
}) {
  useEffect(() => {
    const isValid = data.every(
      (a) =>
        a.resourceId &&
        a.availableFrom &&
        a.availableUntil &&
        new Date(a.availableUntil) > new Date(a.availableFrom)
    );
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const handleAdd = (resourceId) => {
    const newAvail = {
      id: `temp_avail_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      resourceId,
      availableFrom: "",
      availableUntil: "",
    };
    onChange([...data, newAvail]);
  };

  const handleRemove = (id) => {
    onChange(data.filter((a) => a.id !== id));
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((a) => (a.id === id ? { ...a, [field]: value } : a))
    );
  };

  if (resources.length === 0) {
    return (
      <div className="wizard-step-content">
        <h2>Availability</h2>
        <div className="empty-state">
          <Icon name="clock" size={30} />
          <p>Please add resources first to set their availability windows.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step-content">
      <h2>Availability Windows</h2>
      <p className="helper-text">
        Define when each resource is available. You can add multiple windows per resource.
      </p>

      <div className="list-container">
        {resources.map((resource) => {
          const resAvails = data.filter((a) => a.resourceId === resource.id);
          return (
            <div key={resource.id} className="resource-group-card">
              <div className="resource-group-header">
                <h4>{resource.name}</h4>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => handleAdd(resource.id)}
                  title="Add Availability Window"
                >
                  <Icon name="plus" size={16} />
                </button>
              </div>

              {resAvails.length === 0 ? (
                <p className="no-data-text">No specific availability windows added.</p>
              ) : (
                <div className="availability-list">
                  {resAvails.map((avail) => {
                    const isInvalid =
                      avail.availableFrom &&
                      avail.availableUntil &&
                      new Date(avail.availableUntil) <= new Date(avail.availableFrom);

                    return (
                      <div key={avail.id} className="availability-row">
                        <div className="form-group">
                          <label>From <span className="required">*</span></label>
                          <input
                            type="datetime-local"
                            value={avail.availableFrom}
                            onChange={(e) =>
                              handleChange(avail.id, "availableFrom", e.target.value)
                            }
                            className={isInvalid ? "error" : ""}
                          />
                        </div>
                        <div className="form-group">
                          <label>Until <span className="required">*</span></label>
                          <input
                            type="datetime-local"
                            value={avail.availableUntil}
                            onChange={(e) =>
                              handleChange(avail.id, "availableUntil", e.target.value)
                            }
                            className={isInvalid ? "error" : ""}
                          />
                        </div>
                        <button
                          type="button"
                          className="icon-button danger remove-btn"
                          onClick={() => handleRemove(avail.id)}
                          title="Remove Window"
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
