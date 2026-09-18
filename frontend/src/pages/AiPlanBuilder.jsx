import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { parseNaturalLanguagePlan, confirmParsedPlan } from "../services/ai";
import AiExtractedReview from "../components/planner/AiExtractedReview";
import RelevantPlanningContext from "../components/planner/RelevantPlanningContext";

export default function AiPlanBuilder() {
  const navigate = useNavigate();
  const [step, setStep] = useState("INPUT");
  const [inputText, setInputText] = useState("");
  const [error, setError] = useState("");
  const [parsedData, setParsedData] = useState(null);
  const [creating, setCreating] = useState(false);
  async function handleParse(e) {
    e.preventDefault();
    setStep("PARSING"); setError("");
    try {
      const data = await parseNaturalLanguagePlan({ text: inputText });
      if (!data.draft) throw new Error(data.errors?.join("; ") || "No valid planning draft was returned.");
      setParsedData(data); setStep("REVIEW");
    } catch (err) { setError(err.message); setStep("INPUT"); }
  }
  async function handleConfirm() {
    setCreating(true); setError("");
    try {
      const draft = parsedData.draft;
      // Explicit confirmation reviews these fields; backend rechecks all domain rules.
      const answers = [
        ...Object.entries(draft.plan).filter(([, value]) => value != null).map(([key, value]) => ({ field: `plan.${key}`, value })),
        ...["tasks", "resources", "requirements", "dependencies", "constraints"].map(field => ({ field, value: draft[field] || [] })),
        ...Object.entries(draft.custom_values || {}).map(([key, value]) => ({ field: `custom_values.${key}`, value })),
      ];
      const result = await confirmParsedPlan({ confirmed: true, draft, answers });
      if (!Number.isInteger(result.plan_id)) throw new Error("The server returned no plan ID.");
      setParsedData({ ...parsedData, plan_id: result.plan_id }); setStep("CONFIRMED");
    } catch (err) {
      setError(err.message);
      if (err.detail?.questions) setParsedData(current => ({ ...current, questions: err.detail.questions, errors: err.detail.errors || [] }));
    } finally { setCreating(false); }
  }
  return <div className="page-container">
    <header className="page-header"><h1>AI Plan Builder</h1></header>
    {error && <div role="alert" className="alert alert-danger">{error}</div>}
    {step === "INPUT" && <section className="card"><form onSubmit={handleParse}>
      <label htmlFor="nl-input">Describe your planning problem in plain English</label>
      <textarea id="nl-input" className="form-control" style={{ minHeight: 200 }} value={inputText} onChange={e => setInputText(e.target.value)} placeholder="We have 3 developers. Development takes 3 hours." />
      <button className="btn btn-primary" disabled={!inputText.trim()}>Analyze Requirements</button>
    </form></section>}
    {step === "PARSING" && <section className="card"><h2>Understanding your requirements...</h2></section>}
    {step === "REVIEW" && <>
      <p>Review the extracted details below. Make any necessary corrections before confirming.</p>
      {parsedData.errors?.length > 0 && <div role="alert">{parsedData.errors.join("; ")}</div>}
      <AiExtractedReview planData={parsedData} onUpdate={setParsedData} />
      <button className="btn btn-primary" disabled={creating || Boolean(parsedData.reviewError)} onClick={handleConfirm}>{creating ? "Creating..." : "Confirm & Create Plan"}</button>
    </>}
    {step === "CONFIRMED" && <section className="card">
      <h2>Plan created successfully</h2>
      <RelevantPlanningContext planId={parsedData.plan_id} />
      <button className="btn btn-primary" onClick={() => navigate(`/plans/${parsedData.plan_id}/results`)}>Optimize Plan</button>
    </section>}
  </div>;
}
