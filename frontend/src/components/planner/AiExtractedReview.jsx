import { useState } from "react";

export default function AiExtractedReview({ planData, onUpdate }) {
  const data = planData.draft;
  const [jsonError, setJsonError] = useState("");
  function update(path, value, reviewError = planData.reviewError) {
    const draft = structuredClone(data);
    const parts = path.split(".");
    let target = draft;
    for (const part of parts.slice(0, -1)) target = target[part];
    target[parts.at(-1)] = value;
    onUpdate({ ...planData, draft, reviewError });
  }
  function field(path, value, label, numeric = false) {
    return <label key={path} className="form-group">{label}
      <input className="form-control" aria-label={label} type={numeric ? "number" : "text"} value={value ?? ""}
        onChange={e => update(path, e.target.value === "" ? null : numeric ? Number(e.target.value) : e.target.value)} />
    </label>;
  }
  return <div className="ai-extracted-review">
    {planData.questions?.length > 0 && <section className="card"><h2>Needs Confirmation</h2>
      {planData.questions.map(q => <p key={q.id}>{q.question} {q.reason}</p>)}
    </section>}
    <section className="card"><h2>Plan Details</h2>
      {["name", "description", "planning_start", "planning_end"].map(key => field(`plan.${key}`, data.plan[key], `Plan ${key.replaceAll("_", " ")}`))}
      <p>Dates require a full timestamp and timezone, for example 2026-09-18T09:00:00+05:30.</p>
    </section>
    <section className="card"><h2>Resources</h2>{data.resources?.map((r, i) => <div key={r.client_id}>
      {field(`resources.${i}.name`, r.name, `Resource ${i + 1} name`)}
      {field(`resources.${i}.resource_type`, r.resource_type, `Resource ${i + 1} type`)}
      {field(`resources.${i}.capacity`, r.capacity, `Resource ${i + 1} capacity`, true)}
    </div>)}</section>
    <section className="card"><h2>Tasks</h2>{data.tasks?.map((t, i) => <div key={t.client_id}>
      {field(`tasks.${i}.name`, t.name, `Task ${i + 1} name`)}
      {field(`tasks.${i}.duration_value`, t.duration_value, `Task ${i + 1} duration`, true)}
      {field(`tasks.${i}.duration_unit`, t.duration_unit, `Task ${i + 1} unit (seconds, minutes, hours)`)}
      <label>Task {i + 1} priority<select className="form-control" value={t.priority || ""} onChange={e => update(`tasks.${i}.priority`, e.target.value || null)}>
        <option value="">Unspecified</option>{["low", "medium", "high", "critical"].map(v => <option key={v} value={v}>{v}</option>)}
      </select></label>
      {field(`tasks.${i}.earliest_start`, t.earliest_start, `Task ${i + 1} earliest start`)}
      {field(`tasks.${i}.deadline`, t.deadline, `Task ${i + 1} deadline (date and timezone)`)}
      {t.deadline_text && <p>Original deadline: {t.deadline_text}</p>}
    </div>)}</section>
    <section className="card"><h2>Resource Requirements</h2>{data.requirements?.map((r, i) => <div key={i}>
      <p>Task: {data.tasks.find(t => t.client_id === r.task_id)?.name || r.task_id}</p>
      {field(`requirements.${i}.resource_type`, r.resource_type, `Requirement ${i + 1} type`)}
      {field(`requirements.${i}.quantity`, r.quantity, `Requirement ${i + 1} quantity`, true)}
      <p>Specific resource: {data.resources.find(v => v.client_id === r.required_resource_id)?.name || "Any matching resource"}</p>
    </div>)}</section>
    <section className="card"><h2>Dependencies</h2>{data.dependencies?.map((d, i) => <p key={i}>
      {data.tasks.find(t => t.client_id === d.before_task_id)?.name} to {data.tasks.find(t => t.client_id === d.after_task_id)?.name}
    </p>)}</section>
    <section className="card"><h2>Constraints and custom values</h2>
      {jsonError && <p role="alert">{jsonError}</p>}
      {["constraints", "custom_values"].map(key => <label key={key}>{key.replaceAll("_", " ")}
        <textarea className="form-control" defaultValue={JSON.stringify(data[key] || (key === "constraints" ? [] : {}), null, 2)} onBlur={e => {
          try { update(key, JSON.parse(e.target.value), ""); setJsonError(""); } catch { setJsonError("Enter valid JSON before confirming."); onUpdate({ ...planData, reviewError: "Invalid JSON" }); }
        }} />
      </label>)}
    </section>
  </div>;
}
