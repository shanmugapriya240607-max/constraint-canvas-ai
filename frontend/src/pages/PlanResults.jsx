import { useEffect, useState, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { solvePlan, getPlanAnalysis, getSolverRuns, getSolverRun } from "../services/planner";
import StatusHeader from "../components/results/StatusHeader";
import GanttChart from "../components/results/GanttChart";
import PlanHealth from "../components/results/PlanHealth";
import RisksAndBottlenecks from "../components/results/RisksAndBottlenecks";
import InfeasibleView from "../components/results/InfeasibleView";
import SolverHistory from "../components/results/SolverHistory";

export default function PlanResults() {
  const { planId } = useParams();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [analysis, setAnalysis] = useState(null);
  const [solverRuns, setSolverRuns] = useState([]);
  const [latestRunDetail, setLatestRunDetail] = useState(null);
  
  const hasSolvedRef = useRef(false);

  useEffect(() => {
    if (!planId || hasSolvedRef.current) return;
    hasSolvedRef.current = true;

    async function processPlan() {
      try {
        setLoading(true);
        setError(null);
        
        // 1. Trigger the solver
        await solvePlan(planId);
        
        // 2. Fetch the analysis
        const analysisData = await getPlanAnalysis(planId);
        setAnalysis(analysisData);
        
        // 3. Fetch recent solver runs
        const runsData = await getSolverRuns(planId);
        setSolverRuns(runsData);

        // 4. If runs exist and optimal/feasible, fetch latest run detail
        if (runsData && runsData.length > 0 && (analysisData.status === "OPTIMAL" || analysisData.status === "FEASIBLE")) {
          const runDetail = await getSolverRun(planId, runsData[0].id || runsData[0].run_id);
          setLatestRunDetail(runDetail);
        }
        
      } catch (err) {
        console.error("Failed to process plan results:", err);
        setError(err.message || "Failed to solve and analyze the plan.");
      } finally {
        setLoading(false);
      }
    }

    processPlan();
  }, [planId]);

  if (loading) {
    return (
      <div className="results-loading">
        <div className="spinner"></div>
        <h2>Optimizing Plan...</h2>
        <p>This may take a few moments as the solver evaluates constraints.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="results-error">
        <h2>Optimization Failed</h2>
        <div className="notice error">{error}</div>
        <Link to={`/plans/${planId}/edit`} className="btn secondary">Back to Plan</Link>
        <button className="btn primary" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  const { status, health, risks, bottlenecks, recovery_options, issues } = analysis;
  const isInfeasible = status === "INFEASIBLE";

  return (
    <div className="plan-results-page">
      <header className="page-header">
        <div>
          <h1>Plan Optimization Results</h1>
          <p className="text-secondary">Plan ID: {planId}</p>
        </div>
      </header>

      <StatusHeader status={status} health={health} solverRuns={solverRuns} />

      <div className="results-grid">
        <div className="results-main">
          {isInfeasible ? (
            <InfeasibleView issues={issues} recoveryOptions={recovery_options} />
          ) : (
            <GanttChart planId={planId} runDetail={latestRunDetail} />
          )}
        </div>
        
        <aside className="results-sidebar">
          {health && <PlanHealth health={health} />}
          <RisksAndBottlenecks risks={risks} bottlenecks={bottlenecks} />
          <SolverHistory runs={solverRuns} />
        </aside>
      </div>
    </div>
  );
}
