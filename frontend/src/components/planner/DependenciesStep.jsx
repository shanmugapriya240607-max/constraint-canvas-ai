import { useEffect } from "react";
import Icon from "../Icon";

export default function DependenciesStep({
  data,
  tasks,
  onChange,
  onValidationChange,
}) {
  useEffect(() => {
    const isValid = data.every(
      (d) =>
        d.beforeTaskId &&
        d.afterTaskId &&
        d.beforeTaskId !== d.afterTaskId
    );
    onValidationChange(isValid);
  }, [data, onValidationChange]);

  const handleAdd = () => {
    const newDep = {
      id: `temp_dep_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`,
      beforeTaskId: "",
      afterTaskId: "",
    };
    onChange([...data, newDep]);
  };

  const handleRemove = (id) => {
    onChange(data.filter((d) => d.id !== id));
  };

  const handleChange = (id, field, value) => {
    onChange(
      data.map((d) => (d.id === id ? { ...d, [field]: value } : d))
    );
  };

  if (tasks.length < 2) {
    return (
      <div className="wizard-step-content">
        <h2>Dependencies</h2>
        <div className="empty-state">
          <Icon name="link" size={30} />
          <p>Please add at least two tasks to define dependencies between them.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="wizard-step-content">
      <h2>Task Dependencies</h2>
      <p className="helper-text">
        Define which tasks must be completed before others can begin.
      </p>

      {data.length === 0 ? (
        <div className="empty-state small">
          <Icon name="git-commit" size={24} />
          <p>No dependencies defined. Tasks can happen in any order.</p>
        </div>
      ) : (
        <div className="list-container">
          {data.map((dep) => {
            const isSelfDep =
              dep.beforeTaskId &&
              dep.afterTaskId &&
              dep.beforeTaskId === dep.afterTaskId;

            return (
              <div key={dep.id} className="dependency-row">
                <div className="form-group flex-1">
                  <label>Before Task <span className="required">*</span></label>
                  <select
                    value={dep.beforeTaskId}
                    onChange={(e) => handleChange(dep.id, "beforeTaskId", e.target.value)}
                    className={isSelfDep ? "error" : ""}
                  >
                    <option value="">Select Task</option>
                    {tasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.name}
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="dependency-arrow">
                  <Icon name="arrow-right" size={20} />
                </div>

                <div className="form-group flex-1">
                  <label>After Task <span className="required">*</span></label>
                  <select
                    value={dep.afterTaskId}
                    onChange={(e) => handleChange(dep.id, "afterTaskId", e.target.value)}
                    className={isSelfDep ? "error" : ""}
                  >
                    <option value="">Select Task</option>
                    {tasks.map((task) => (
                      <option key={task.id} value={task.id}>
                        {task.name}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  className="icon-button danger remove-btn mt-20"
                  onClick={() => handleRemove(dep.id)}
                  title="Remove Dependency"
                >
                  <Icon name="trash-2" size={16} />
                </button>
                
                {isSelfDep && (
                  <div className="error-message full-width">
                    A task cannot depend on itself.
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <button type="button" className="button secondary add-button" onClick={handleAdd}>
        <Icon name="plus" size={16} /> Add Dependency
      </button>
    </div>
  );
}
