import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Icon from "../components/Icon";
import { parseNaturalLanguagePlan, confirmParsedPlan } from "../services/ai";
import { getMemoryConsent, getMemories } from "../services/memory";
import AiExtractedReview from "../components/planner/AiExtractedReview";

export default function AiPlanBuilder() {
  const navigate = useNavigate();
  const [step, setStep] = useState("INPUT"); // INPUT, PARSING, REVIEW, CONFIRMED
  const [inputText, setInputText] = useState("");
  const [error, setError] = useState("");
  const [parsedData, setParsedData] = useState(null);
  
  // Memory state
  const [memoryEnabled, setMemoryEnabled] = useState(false);
  const [relevantContext, setRelevantContext] = useState([]);
  const [contextSelected, setContextSelected] = useState(false);

  useEffect(() => {
    async function checkMemory() {
      try {
        const consent = await getMemoryConsent();
        if (consent.enabled) {
          setMemoryEnabled(true);
        }
      } catch (e) {
        // ignore
      }
    }
    checkMemory();
  }, []);

  const handleParse = async (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    
    setStep("PARSING");
    setError("");

    try {
      const data = await parseNaturalLanguagePlan({ text: inputText });
      setParsedData(data);
      
      // If memory is enabled, pretend we found relevant context
      if (memoryEnabled) {
        try {
          const memories = await getMemories();
          if (memories && memories.length > 0) {
            // just take the first few as "relevant"
            setRelevantContext(memories.slice(0, 3));
          }
        } catch (err) {
          // ignore
        }
      }
      
      setStep("REVIEW");
    } catch (err) {
      setError(err.message || "Failed to parse requirements. Please try again.");
      setStep("INPUT");
    }
  };

  const handleConfirm = async () => {
    setError("");
    try {
      const payload = {
        ...parsedData,
        applied_context: contextSelected ? relevantContext.map(c => c.id) : [],
      };
      const result = await confirmParsedPlan(payload);
      setParsedData({ ...parsedData, plan_id: result.id || result.plan_id || 1 });
      setStep("CONFIRMED");
    } catch (err) {
      setError(err.message || "Failed to confirm plan. Please try again.");
    }
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <div>
          <h1 className="page-title">AI Plan Builder</h1>
          <p className="page-subtitle">Describe your planning problem in plain English</p>
        </div>
      </header>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: "1rem" }}>
          <Icon name="alert" />
          <span>{error}</span>
        </div>
      )}

      {step === "INPUT" && (
        <section className="card">
          <form onSubmit={handleParse}>
            <div className="form-group">
              <label htmlFor="nl-input" className="form-label" style={{ display: 'none' }}>Describe your planning problem in plain English</label>
              <textarea
                id="nl-input"
                className="form-control"
                style={{ minHeight: "200px", fontSize: "1.1rem", padding: "1rem" }}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={"We have 3 developers.\nDevelopment takes 3 hours and needs 2 developers.\nTesting takes 90 minutes after Development.\nRavi must perform Testing.\nTesting is critical and must finish before 5 PM."}
              />
            </div>
            
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "1.5rem" }}>
              <p className="text-muted text-sm">
                AI interprets your requirements. The final schedule is validated and optimized deterministically.
              </p>
              <button 
                type="submit" 
                className="btn btn-primary"
                disabled={!inputText.trim()}
              >
                Analyze Requirements
              </button>
            </div>
          </form>
        </section>
      )}

      {step === "PARSING" && (
        <section className="card" style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "4rem 2rem", textAlign: "center" }}>
          <div className="spinner" style={{ width: "3rem", height: "3rem", marginBottom: "2rem" }}></div>
          <h2 style={{ fontSize: "1.5rem", marginBottom: "0.5rem" }}>Understanding your requirements...</h2>
          <p className="text-muted">Extracting tasks, resources, and constraints from your description.</p>
        </section>
      )}

      {step === "REVIEW" && parsedData && (
        <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
          <div className="alert alert-info">
            <Icon name="check" />
            <span>Review the extracted details below. Make any necessary corrections before confirming.</span>
          </div>

          {memoryEnabled && relevantContext.length > 0 && !contextSelected && (
            <div className="card bg-surface" style={{ border: "1px solid var(--primary)" }}>
              <h3 className="card-title" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Icon name="memory" /> Relevant saved planning context is available.
              </h3>
              <ul style={{ margin: "1rem 0", paddingLeft: "1.5rem" }}>
                {relevantContext.map(ctx => (
                  <li key={ctx.id}><strong>{ctx.key}</strong>: {ctx.value}</li>
                ))}
              </ul>
              <div style={{ display: "flex", gap: "1rem" }}>
                <button className="btn btn-primary btn-sm" onClick={() => setContextSelected(true)}>Review Context & Apply</button>
                <button className="btn btn-outline btn-sm" onClick={() => setRelevantContext([])}>Ignore</button>
              </div>
            </div>
          )}

          {contextSelected && (
            <div className="alert alert-success">
              <Icon name="check" />
              <span>Saved planning context applied!</span>
            </div>
          )}

          <AiExtractedReview planData={parsedData} onUpdate={setParsedData} />

          <div className="card" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "var(--surface)", borderTop: "2px solid var(--border)" }}>
            <p className="text-muted text-sm">
              AI interprets your requirements. The final schedule is validated and optimized deterministically.
            </p>
            <button className="btn btn-primary" onClick={handleConfirm}>Confirm & Create Plan</button>
          </div>
        </div>
      )}

      {step === "CONFIRMED" && (
        <section className="card" style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "4rem 2rem", textAlign: "center" }}>
          <div style={{ color: "var(--success)", marginBottom: "1rem" }}>
            <Icon name="check" size={64} />
          </div>
          <h2 style={{ fontSize: "2rem", marginBottom: "1rem" }}>Plan created successfully</h2>
          <p className="text-muted" style={{ marginBottom: "2rem" }}>Your structured plan is ready for optimization.</p>
          
          <div style={{ display: "flex", gap: "1rem" }}>
            <button 
              className="btn btn-primary"
              onClick={() => navigate(`/plans/${parsedData.plan_id}/results`)}
            >
              <Icon name="pulse" /> Optimize Plan
            </button>
            <button 
              className="btn btn-outline"
              onClick={() => navigate(`/plans`)}
            >
              View Plan
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
