import { useState, useEffect } from "react";
import Icon from "../components/Icon";
import {
  getMemoryConsent,
  updateMemoryConsent,
  getMemories,
  createMemory,
  deleteMemory,
  getHabitCandidates,
  acceptHabit,
  rejectHabit,
  detectHabits,
} from "../services/memory";

export default function Memory() {
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(true);
  const [memories, setMemories] = useState([]);
  const [habits, setHabits] = useState([]);
  const [error, setError] = useState("");

  // Form state
  const [newType, setNewType] = useState("preference");
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    try {
      const c = await getMemoryConsent();
      setConsent(c.memory_enabled);
      const m = await getMemories();
      setMemories(m);
      const h = await getHabitCandidates();
      setHabits(h.filter(item => item.status === "pending"));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleToggleConsent() {
    try {
      const nextConsent = !consent;
      await updateMemoryConsent(nextConsent);
      setConsent(nextConsent);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleCreateMemory(e) {
    e.preventDefault();
    if (!newKey || !newValue) return;
    try {
      await createMemory({ memory_type: newType, key: newKey, value: { text: newValue }, source: "explicit" });
      setNewKey("");
      setNewValue("");
      const m = await getMemories();
      setMemories(m);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleDeleteMemory(id) {
    try {
      await deleteMemory(id);
      const m = await getMemories();
      setMemories(m);
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleAcceptHabit(id) {
    try {
      await acceptHabit(id);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleRejectHabit(id) {
    try {
      await rejectHabit(id);
      await loadData();
    } catch (e) {
      setError(e.message);
    }
  }

  async function handleDetectHabits() {
    try {
      await detectHabits();
      const h = await getHabitCandidates();
      setHabits(h.filter(item => item.status === "pending"));
    } catch (e) {
      setError(e.message);
    }
  }

  if (loading) {
    return <div className="page-container"><p>Loading...</p></div>;
  }

  return (
    <div className="page-container">
      {error && <div role="alert" className="notice error">{error}</div>}
      <header className="page-header">
        <div>
          <h1 className="page-title">Planning Memory</h1>
          <p className="page-subtitle">Allow ConstraintCanvas AI to remember approved planning information for future planning.</p>
        </div>
      </header>

      <section className="card" style={{ marginBottom: "2rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <h2 className="card-title">Memory Consent</h2>
            <p className="text-muted">
              It may remember resource preferences, availability preferences, working hours, preferred resources, preferred times, and reusable planning constraints.
            </p>
          </div>
          <button 
            className={`btn ${consent ? "btn-danger" : "btn-primary"}`}
            onClick={handleToggleConsent}
          >
            {consent ? "Disable Memory" : "Enable Memory"}
          </button>
        </div>
        {!consent && (
          <div className="alert alert-warning" style={{ marginTop: "1rem" }}>
            <Icon name="warning" />
            <span>Planning memory is off. Your saved preferences will not be reused for future planning.</span>
          </div>
        )}
      </section>

      <section className="card" style={{ marginBottom: "2rem" }}>
        <h2 className="card-title">Add Explicit Memory</h2>
        <form onSubmit={handleCreateMemory} style={{ display: "flex", flexWrap: "wrap", gap: "1rem", alignItems: "flex-end" }}>
          <div className="form-group" style={{ flex: "1 1 160px", minWidth: 0, marginBottom: 0 }}>
            <label htmlFor="memory-type" className="form-label">Type</label>
            <select id="memory-type" className="form-control" value={newType} onChange={(e) => setNewType(e.target.value)}>
              <option value="preference">Preference</option>
              <option value="constraint">Constraint</option>
              <option value="working_hours">Working Hours</option>
            </select>
          </div>
          <div className="form-group" style={{ flex: "2 1 180px", minWidth: 0, marginBottom: 0 }}>
            <label htmlFor="memory-key" className="form-label">Key (e.g. Preferred Tester)</label>
            <input id="memory-key" className="form-control" value={newKey} onChange={(e) => setNewKey(e.target.value)} required />
          </div>
          <div className="form-group" style={{ flex: "2 1 180px", minWidth: 0, marginBottom: 0 }}>
            <label htmlFor="memory-value" className="form-label">Value (e.g. Ravi)</label>
            <input id="memory-value" className="form-control" value={newValue} onChange={(e) => setNewValue(e.target.value)} required />
          </div>
          <button type="submit" disabled={!consent} className="btn btn-primary" style={{ marginBottom: 0 }}>Save</button>
        </form>
      </section>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: "2rem" }}>
        <section className="card">
          <h2 className="card-title">Suggested Habits</h2>
          <div style={{ marginBottom: "1rem" }}>
            <button className="btn btn-outline" onClick={handleDetectHabits}>Detect New Habits</button>
          </div>
          {habits.length === 0 ? (
            <p className="text-muted">No pending habit suggestions.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {habits.map(habit => (
                <div key={habit.id} className="card bg-surface" style={{ padding: "1rem", border: "1px solid var(--border)" }}>
                  <p style={{ marginBottom: "1rem" }}>{`We noticed a pattern: ${habit.normalized_pattern}`}</p>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button className="btn btn-primary btn-sm" onClick={() => handleAcceptHabit(habit.id)}>Remember This</button>
                    <button className="btn btn-outline btn-sm" onClick={() => handleRejectHabit(habit.id)}>Reject</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="card">
          <h2 className="card-title">Saved Memories</h2>
          {memories.length === 0 ? (
            <p className="text-muted">No saved memories found.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {memories.map(mem => (
                <div key={mem.id} className="card bg-surface" style={{ padding: "1rem", border: "1px solid var(--border)", display: "flex", justifyContent: "space-between" }}>
                  <div>
                    <strong>{mem.key}</strong>: {mem.value?.text ?? JSON.stringify(mem.value)}
                    <div className="text-muted text-sm" style={{ marginTop: "0.5rem" }}>
                      Type: {mem.memory_type} | Source: {mem.source}
                      {mem.confidence && ` | Confidence: ${(mem.confidence * 100).toFixed(0)}%`}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem" }}>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteMemory(mem.id)}>
                      <Icon name="delete" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
