export default function ReviewStep({ wizardState, onEditStep }) {
  const {
    planDetails,
    resources,
    availabilities,
    tasks,
    requirements,
    dependencies,
    constraints,
  } = wizardState;

  const findTaskName = (id) => tasks.find((t) => t.id === id)?.name || "Unknown";
  const findResName = (id) => resources.find((r) => r.id === id)?.name || "Unknown";

  return (
    <div className="wizard-step-content review-step">
      <h2>Review Your Plan</h2>
      <p className="helper-text">
        Review all information below. You can go back to edit any section.
      </p>

      <section className="review-section">
        <div className="section-header">
          <h3>Plan Details</h3>
          <button type="button" className="text-button" onClick={() => onEditStep(0)}>Edit</button>
        </div>
        <div className="summary-grid">
          <div className="summary-item">
            <label>Name</label>
            <span>{planDetails.name}</span>
          </div>
          {planDetails.description && (
            <div className="summary-item full-width">
              <label>Description</label>
              <span>{planDetails.description}</span>
            </div>
          )}
          <div className="summary-item">
            <label>Planning Start</label>
            <span>{new Date(planDetails.planningStart).toLocaleString()}</span>
          </div>
          <div className="summary-item">
            <label>Planning End</label>
            <span>{new Date(planDetails.planningEnd).toLocaleString()}</span>
          </div>
        </div>
      </section>

      <section className="review-section">
        <div className="section-header">
          <h3>Resources & Availability</h3>
          <button type="button" className="text-button" onClick={() => onEditStep(1)}>Edit</button>
        </div>
        {resources.length === 0 ? (
          <p className="no-data-text">No resources added.</p>
        ) : (
          <ul className="summary-list">
            {resources.map((r) => {
              const resAvails = availabilities.filter((a) => a.resourceId === r.id);
              return (
                <li key={r.id}>
                  <strong>{r.name}</strong> ({r.type}) - Cap: {r.capacity}
                  {resAvails.length > 0 && (
                    <ul>
                      {resAvails.map((a) => (
                        <li key={a.id}>
                          {new Date(a.availableFrom).toLocaleString()} to {new Date(a.availableUntil).toLocaleString()}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="review-section">
        <div className="section-header">
          <h3>Tasks & Requirements</h3>
          <button type="button" className="text-button" onClick={() => onEditStep(3)}>Edit</button>
        </div>
        {tasks.length === 0 ? (
          <p className="no-data-text">No tasks added.</p>
        ) : (
          <ul className="summary-list">
            {tasks.map((t) => {
              const reqs = requirements.filter((req) => req.taskId === t.id);
              return (
                <li key={t.id}>
                  <strong>{t.name}</strong> - {t.durationValue} {t.durationUnit} ({t.priority})
                  {t.earliestStart && <span> | Earliest: {new Date(t.earliestStart).toLocaleString()}</span>}
                  {t.deadline && <span> | Deadline: {new Date(t.deadline).toLocaleString()}</span>}
                  {reqs.length > 0 && (
                    <ul>
                      {reqs.map((req) => (
                        <li key={req.id}>
                          Requires {req.quantity}x {req.resourceType}
                          {req.specificResourceId && ` (Specific: ${findResName(req.specificResourceId)})`}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="review-section">
        <div className="section-header">
          <h3>Dependencies</h3>
          <button type="button" className="text-button" onClick={() => onEditStep(5)}>Edit</button>
        </div>
        {dependencies.length === 0 ? (
          <p className="no-data-text">No dependencies.</p>
        ) : (
          <ul className="summary-list">
            {dependencies.map((d) => (
              <li key={d.id}>
                {findTaskName(d.beforeTaskId)} <strong>→</strong> {findTaskName(d.afterTaskId)}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="review-section">
        <div className="section-header">
          <h3>Constraints</h3>
          <button type="button" className="text-button" onClick={() => onEditStep(6)}>Edit</button>
        </div>
        {constraints.length === 0 ? (
          <p className="no-data-text">No custom constraints.</p>
        ) : (
          <ul className="summary-list">
            {constraints.map((c) => (
              <li key={c.id}>
                <strong>{c.type.replace(/_/g, " ")}</strong> ({c.hardness})
                {c.hardness === "soft" && ` [Wt: ${c.weight}]`}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
