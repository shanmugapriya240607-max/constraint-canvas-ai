import { useState, useEffect } from "react";

export default function PlanDetailsStep({ data, onChange, onValidationChange }) {
  const [errors, setErrors] = useState({});

  useEffect(() => {
    const newErrors = {};
    if (!data.name || !data.name.trim()) {
      newErrors.name = "Plan name is required";
    }
    
    if (!data.planningStart) {
      newErrors.planningStart = "Start time is required";
    }
    
    if (!data.planningEnd) {
      newErrors.planningEnd = "End time is required";
    } else if (
      data.planningStart &&
      new Date(data.planningEnd) <= new Date(data.planningStart)
    ) {
      newErrors.planningEnd = "End time must be later than start time";
    }

    setErrors(newErrors);
    onValidationChange(Object.keys(newErrors).length === 0);
  }, [data, onValidationChange]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    onChange({ ...data, [name]: value });
  };

  return (
    <div className="wizard-step-content">
      <h2>Plan Details</h2>
      <p className="helper-text">
        Define the high-level information for your new planning problem.
      </p>

      <div className="form-group">
        <label htmlFor="name">
          Plan Name <span className="required">*</span>
        </label>
        <input
          type="text"
          id="name"
          name="name"
          value={data.name}
          onChange={handleChange}
          placeholder="e.g. Q3 Software Release"
          className={errors.name ? "error" : ""}
        />
        {errors.name && <span className="error-message">{errors.name}</span>}
      </div>

      <div className="form-group">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          name="description"
          value={data.description}
          onChange={handleChange}
          placeholder="Optional overview of the planning goals"
          rows="3"
        />
      </div>

      <div className="form-row">
        <div className="form-group half">
          <label htmlFor="planningStart">
            Planning Start <span className="required">*</span>
          </label>
          <input
            type="datetime-local"
            id="planningStart"
            name="planningStart"
            value={data.planningStart}
            onChange={handleChange}
            className={errors.planningStart ? "error" : ""}
          />
          {errors.planningStart && (
            <span className="error-message">{errors.planningStart}</span>
          )}
        </div>

        <div className="form-group half">
          <label htmlFor="planningEnd">
            Planning End <span className="required">*</span>
          </label>
          <input
            type="datetime-local"
            id="planningEnd"
            name="planningEnd"
            value={data.planningEnd}
            onChange={handleChange}
            className={errors.planningEnd ? "error" : ""}
          />
          {errors.planningEnd && (
            <span className="error-message">{errors.planningEnd}</span>
          )}
        </div>
      </div>
    </div>
  );
}
