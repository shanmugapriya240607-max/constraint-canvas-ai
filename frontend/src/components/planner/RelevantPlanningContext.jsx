import { useState, useEffect } from "react";
import { getPlanContext, applyPlanContext } from "../../services/memory";

export default function RelevantPlanningContext({ planId, onApplied }) {
  const [contextItems, setContextItems] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (planId) {
      loadContext();
    }
  }, [planId]);

  async function loadContext() {
    setLoading(true);
    try {
      const data = await getPlanContext(planId);
      setContextItems(data.items || data || []);
      const initialSelected = new Set((data.items || data || []).map(i => i.id));
      setSelectedIds(initialSelected);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleApply() {
    if (selectedIds.size === 0) return;
    try {
      await applyPlanContext(planId, Array.from(selectedIds));
      if (onApplied) onApplied();
    } catch (err) {
      setError(err.message);
    }
  }

  function handleIgnore() {
    if (onApplied) onApplied();
  }

  function toggleSelection(id) {
    const newSelection = new Set(selectedIds);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedIds(newSelection);
  }

  if (loading) return <div>Loading relevant context...</div>;
  if (error) return <div className="text-danger">Failed to load context: {error}</div>;
  if (!contextItems || contextItems.length === 0) return null;

  return (
    <div className="card bg-surface" style={{ marginBottom: "1rem" }}>
      <h3 className="card-title">Relevant Planning Context Found</h3>
      <p className="text-muted" style={{ marginBottom: "1rem" }}>
        We found the following saved preferences that might apply to this plan:
      </p>
      
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1rem" }}>
        {contextItems.map(item => (
          <label key={item.id} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <input 
              type="checkbox" 
              checked={selectedIds.has(item.id)}
              onChange={() => toggleSelection(item.id)}
            />
            <span>• {item.value || `${item.key}: ${item.value}`}</span>
          </label>
        ))}
      </div>

      <div style={{ display: "flex", gap: "1rem" }}>
        <button 
          className="btn btn-primary btn-sm" 
          onClick={handleApply}
          disabled={selectedIds.size === 0}
        >
          Use Selected
        </button>
        <button className="btn btn-outline btn-sm" onClick={handleIgnore}>
          Ignore
        </button>
      </div>
    </div>
  );
}
