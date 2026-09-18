import { useState } from "react";
import Icon from "../Icon";

export default function AiExtractedReview({ planData, onUpdate }) {
  const [data, setData] = useState(planData);

  const handleTaskChange = (index, field, value) => {
    const newTasks = [...data.tasks];
    newTasks[index] = { ...newTasks[index], [field]: value };
    const newData = { ...data, tasks: newTasks };
    setData(newData);
    onUpdate(newData);
  };

  const handleResourceChange = (index, field, value) => {
    const newResources = [...data.resources];
    newResources[index] = { ...newResources[index], [field]: value };
    const newData = { ...data, resources: newResources };
    setData(newData);
    onUpdate(newData);
  };

  const handleMissingInfoChange = (index, value) => {
    const newMissing = [...(data.missing_information || [])];
    newMissing[index] = { ...newMissing[index], provided_answer: value };
    const newData = { ...data, missing_information: newMissing };
    setData(newData);
    onUpdate(newData);
  };

  return (
    <div className="ai-extracted-review" style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      {data.missing_information && data.missing_information.length > 0 && (
        <section className="card" style={{ border: "2px solid var(--primary)" }}>
          <h2 className="card-title" style={{ color: "var(--primary)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Icon name="alert" /> Needs Confirmation
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem", marginTop: "1rem" }}>
            {data.missing_information.map((item, idx) => (
              <div key={idx} className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" htmlFor={`missing-info-${idx}`}>{item.question || item.field}</label>
                <input
                  id={`missing-info-${idx}`}
                  className="form-control"
                  value={item.provided_answer || ""}
                  onChange={(e) => handleMissingInfoChange(idx, e.target.value)}
                  placeholder="Your answer..."
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {data.plan_details && Object.keys(data.plan_details).length > 0 && (
        <section className="card">
          <h2 className="card-title">Plan Details</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            {Object.entries(data.plan_details).map(([key, value]) => (
              <div key={key} className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" style={{ textTransform: "capitalize" }}>{key.replace(/_/g, " ")}</label>
                <input
                  className="form-control"
                  value={value || ""}
                  onChange={(e) => {
                    const newDetails = { ...data.plan_details, [key]: e.target.value };
                    const newData = { ...data, plan_details: newDetails };
                    setData(newData);
                    onUpdate(newData);
                  }}
                />
              </div>
            ))}
          </div>
        </section>
      )}

      {data.resources && data.resources.length > 0 && (
        <section className="card">
          <h2 className="card-title">Resources</h2>
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Capacity/Quantity</th>
                </tr>
              </thead>
              <tbody>
                {data.resources.map((res, idx) => (
                  <tr key={idx}>
                    <td>
                      <input className="form-control" value={res.name || ""} onChange={(e) => handleResourceChange(idx, "name", e.target.value)} />
                    </td>
                    <td>
                      <input className="form-control" value={res.type || ""} onChange={(e) => handleResourceChange(idx, "type", e.target.value)} />
                    </td>
                    <td>
                      <input className="form-control" type="number" value={res.capacity || res.quantity || ""} onChange={(e) => handleResourceChange(idx, res.capacity !== undefined ? "capacity" : "quantity", e.target.value)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data.tasks && data.tasks.length > 0 && (
        <section className="card">
          <h2 className="card-title">Tasks</h2>
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Duration</th>
                  <th>Priority</th>
                  <th>Deadline</th>
                </tr>
              </thead>
              <tbody>
                {data.tasks.map((task, idx) => (
                  <tr key={idx}>
                    <td>
                      <input className="form-control" value={task.name || ""} onChange={(e) => handleTaskChange(idx, "name", e.target.value)} />
                    </td>
                    <td>
                      <input className="form-control" value={task.duration || ""} onChange={(e) => handleTaskChange(idx, "duration", e.target.value)} placeholder="e.g. 3 hours" />
                    </td>
                    <td>
                      <select className="form-control" value={task.priority || "Medium"} onChange={(e) => handleTaskChange(idx, "priority", e.target.value)}>
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Critical">Critical</option>
                      </select>
                    </td>
                    <td>
                      <input className="form-control" value={task.deadline || ""} onChange={(e) => handleTaskChange(idx, "deadline", e.target.value)} placeholder="e.g. 5:00 PM" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {data.dependencies && data.dependencies.length > 0 && (
        <section className="card">
          <h2 className="card-title">Dependencies</h2>
          <ul style={{ paddingLeft: "1.5rem", marginTop: "0.5rem" }}>
            {data.dependencies.map((dep, idx) => (
              <li key={idx} style={{ marginBottom: "0.25rem" }}>
                <strong>{dep.from}</strong> &rarr; <strong>{dep.to}</strong> {dep.type ? `(${dep.type})` : ""}
              </li>
            ))}
          </ul>
        </section>
      )}

      {data.custom_fields && data.custom_fields.length > 0 && (
        <section className="card">
          <h2 className="card-title">Additional Constraints</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1rem", marginTop: "1rem" }}>
            {data.custom_fields.map((field, idx) => (
              <div key={idx} className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label" htmlFor={`custom-field-${idx}`}>{field.label || field.key}</label>
                <input
                  id={`custom-field-${idx}`}
                  className="form-control"
                  type={field.type === "number" ? "number" : "text"}
                  value={field.value || ""}
                  onChange={(e) => {
                    const newCustom = [...data.custom_fields];
                    newCustom[idx] = { ...newCustom[idx], value: e.target.value };
                    const newData = { ...data, custom_fields: newCustom };
                    setData(newData);
                    onUpdate(newData);
                  }}
                  placeholder={field.placeholder || ""}
                />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
