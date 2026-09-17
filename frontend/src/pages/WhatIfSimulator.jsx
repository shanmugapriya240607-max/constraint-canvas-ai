import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { 
  getPlans, 
  getPlanAnalysis, 
  getSolverRuns, 
  getSolverRun,
  getResources,
  getTasks
} from "../services/planner";
import { runWhatIf, compareScenarios } from "../api";
import StatusHeader from "../components/results/StatusHeader";
import GanttChart from "../components/results/GanttChart";
import PlanHealth from "../components/results/PlanHealth";
import RisksAndBottlenecks from "../components/results/RisksAndBottlenecks";
import InfeasibleView from "../components/results/InfeasibleView";
import Icon from "../components/Icon";

export default function WhatIfSimulator() {
  const { planId } = useParams();
  const navigate = useNavigate();
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [plans, setPlans] = useState([]);
  
  // Baseline data
  const [baselineAnalysis, setBaselineAnalysis] = useState(null);
  const [baselineRunDetail, setBaselineRunDetail] = useState(null);
  const [baselineSolverRuns, setBaselineSolverRuns] = useState([]);
  const [resources, setResources] = useState([]);
  const [tasks, setTasks] = useState([]);
  
  // Simulation State
  const [changes, setChanges] = useState([]);
  const [simulationResult, setSimulationResult] = useState(null);
  const [runningSim, setRunningSim] = useState(false);
  
  // Comparison State
  const [activeTab, setActiveTab] = useState("simulator"); // simulator | comparison
  const [scenarios, setScenarios] = useState([]);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [runningComp, setRunningComp] = useState(false);

  // Load available plans if no plan is selected
  useEffect(() => {
    if (!planId) {
      async function loadPlans() {
        try {
          const fetchedPlans = await getPlans();
          setPlans(fetchedPlans);
        } catch (err) {
          console.error("Failed to load plans", err);
        }
      }
      loadPlans();
    }
  }, [planId]);

  // Load baseline data when planId changes
  useEffect(() => {
    if (!planId) return;
    async function loadBaseline() {
      setLoading(true);
      try {
        const [analysis, runs, res, tsk] = await Promise.all([
          getPlanAnalysis(planId),
          getSolverRuns(planId),
          getResources(planId),
          getTasks(planId)
        ]);
        setBaselineAnalysis(analysis);
        setBaselineSolverRuns(runs);
        setResources(res);
        setTasks(tsk);
        
        if (runs && runs.length > 0 && (analysis.status === "OPTIMAL" || analysis.status === "FEASIBLE")) {
          const runDetail = await getSolverRun(planId, runs[0].id || runs[0].run_id);
          setBaselineRunDetail(runDetail);
        }
      } catch (err) {
        setError(err.message || "Failed to load baseline data");
      } finally {
        setLoading(false);
      }
    }
    loadBaseline();
    
    // Reset state
    setChanges([]);
    setSimulationResult(null);
    setScenarios([]);
    setComparisonResult(null);
    setActiveTab("simulator");
  }, [planId]);

  const addChange = (type) => {
    let newChange = { type, id: crypto.randomUUID() };
    switch(type) {
      case "resource_unavailable":
      case "resource_capacity_change":
      case "resource_availability_change":
        newChange.resource_id = "";
        break;
      case "deadline_change":
      case "priority_change":
      case "task_duration_change":
        newChange.task_id = "";
        break;
      case "add_temporary_resource":
        newChange.name = "";
        newChange.resource_type = "developer";
        newChange.capacity = 1;
        break;
    }
    setChanges([...changes, newChange]);
  };

  const removeChange = (id) => {
    setChanges(changes.filter(c => c.id !== id));
  };

  const updateChange = (id, field, value) => {
    setChanges(changes.map(c => {
      if (c.id === id) {
        let updated = { ...c, [field]: value };
        if (field === 'type') {
          // Initialize defaults for the new type
          if (value === 'resource_unavailable' || value === 'resource_capacity_change' || value === 'resource_availability_change') {
            updated.resource_id = updated.resource_id || "";
          }
          if (value === 'deadline_change' || value === 'priority_change' || value === 'task_duration_change') {
            updated.task_id = updated.task_id || "";
          }
          if (value === 'add_temporary_resource') {
            updated.name = updated.name || "";
            updated.resource_type = updated.resource_type || "developer";
            updated.capacity = updated.capacity || 1;
          }
        }
        return updated;
      }
      return c;
    }));
  };

  const validateChanges = () => {
    if (changes.length === 0) {
      setError("Please add at least one change.");
      return false;
    }
    setError(null);
    return true;
  };

  const handleRunSimulation = async () => {
    if (!validateChanges()) return;
    
    const payloadChanges = changes.map(({id, ...c}) => {
      const formatted = { ...c };
      if (formatted.type === "task_duration_change") {
        let mins = parseFloat(formatted.duration_value);
        if (formatted.duration_unit === "hours") mins *= 60;
        formatted.duration_minutes = Math.round(mins);
        delete formatted.duration_value;
        delete formatted.duration_unit;
      }
      if (formatted.deadline) {
        formatted.deadline = new Date(formatted.deadline).toISOString();
      }
      if (formatted.available_from) formatted.available_from = new Date(formatted.available_from).toISOString();
      if (formatted.available_until) formatted.available_until = new Date(formatted.available_until).toISOString();
      return formatted;
    });

    setRunningSim(true);
    try {
      const res = await runWhatIf(planId, { changes: payloadChanges });
      setSimulationResult(res);
    } catch (err) {
      setError(err.message || "Simulation failed.");
    } finally {
      setRunningSim(false);
    }
  };

  const handleSaveScenario = (name) => {
    if (!name.trim() || changes.length === 0) return;
    setScenarios([...scenarios, { name, changes: [...changes] }]);
  };

  const handleRunComparison = async () => {
    if (scenarios.length === 0) return;
    const payload = {
      scenarios: scenarios.map(s => {
        return {
          name: s.name,
          changes: s.changes.map(({id, ...c}) => {
            const formatted = { ...c };
            if (formatted.type === "task_duration_change") {
              let mins = parseFloat(formatted.duration_value);
              if (formatted.duration_unit === "hours") mins *= 60;
              formatted.duration_minutes = Math.round(mins);
              delete formatted.duration_value;
              delete formatted.duration_unit;
            }
            if (formatted.deadline) formatted.deadline = new Date(formatted.deadline).toISOString();
            if (formatted.available_from) formatted.available_from = new Date(formatted.available_from).toISOString();
            if (formatted.available_until) formatted.available_until = new Date(formatted.available_until).toISOString();
            return formatted;
          })
        };
      })
    };

    setRunningComp(true);
    try {
      const res = await compareScenarios(planId, payload);
      setComparisonResult(res);
    } catch (err) {
      setError(err.message || "Comparison failed.");
    } finally {
      setRunningComp(false);
    }
  };

  // UI rendering logic...
  if (!planId) {
    return (
      <div className="container">
        <header className="page-header">
          <h1>Select a Plan for What-If Analysis</h1>
        </header>
        <div className="card">
          {plans.length === 0 ? (
            <p>No plans available. Create a plan first.</p>
          ) : (
            <ul className="plan-list">
              {plans.map(p => (
                <li key={p.id || p.plan_id}>
                  <button className="button primary" onClick={() => navigate(`/plans/${p.id || p.plan_id}/what-if`)}>
                    {p.name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return <div className="loading"><div className="spinner"></div></div>;
  }

  return (
    <div className="what-if-page">
      <header className="page-header">
        <div>
          <h1>What-If Simulator</h1>
          <p className="text-secondary">Plan ID: {planId} <span className="tag warning">Simulation only — the original plan remains unchanged.</span></p>
        </div>
        <div className="tabs">
          <button className={`tab ${activeTab === 'simulator' ? 'active' : ''}`} onClick={() => setActiveTab('simulator')}>Simulator</button>
          <button className={`tab ${activeTab === 'comparison' ? 'active' : ''}`} onClick={() => setActiveTab('comparison')}>Compare Scenarios</button>
        </div>
      </header>

      {error && <div className="notice error">{error}</div>}

      {activeTab === 'simulator' && (
        <div className="simulator-view">
          <div className="builder-sidebar">
            <h3>Change Builder</h3>
            <div className="changes-list">
              {changes.map((c, i) => (
                <div key={c.id} className="change-item card">
                  <div className="change-header">
                    <h4>Change {i + 1}</h4>
                    <button className="button icon-only" onClick={() => removeChange(c.id)}><Icon name="close" /></button>
                  </div>
                  <select value={c.type} onChange={(e) => updateChange(c.id, 'type', e.target.value)}>
                    <option value="resource_unavailable">Resource Unavailable</option>
                    <option value="resource_capacity_change">Resource Capacity Change</option>
                    <option value="resource_availability_change">Resource Availability Change</option>
                    <option value="deadline_change">Deadline Change</option>
                    <option value="priority_change">Priority Change</option>
                    <option value="task_duration_change">Task Duration Change</option>
                    <option value="add_temporary_resource">Add Temporary Resource</option>
                  </select>

                  {(c.type === 'resource_unavailable' || c.type === 'resource_capacity_change' || c.type === 'resource_availability_change') && (
                    <select value={c.resource_id} onChange={(e) => updateChange(c.id, 'resource_id', e.target.value)}>
                      <option value="">[Select Resource]</option>
                      {resources.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
                    </select>
                  )}

                  {(c.type === 'deadline_change' || c.type === 'priority_change' || c.type === 'task_duration_change') && (
                    <select value={c.task_id} onChange={(e) => updateChange(c.id, 'task_id', e.target.value)}>
                      <option value="">[Select Task]</option>
                      {tasks.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  )}

                  {c.type === 'resource_capacity_change' && (
                    <input type="number" min="1" placeholder="New Capacity" value={c.capacity || ''} onChange={(e) => updateChange(c.id, 'capacity', parseInt(e.target.value))} />
                  )}

                  {c.type === 'deadline_change' && (
                    <input type="datetime-local" value={c.deadline || ''} onChange={(e) => updateChange(c.id, 'deadline', e.target.value)} />
                  )}

                  {c.type === 'priority_change' && (
                    <select value={c.priority || 'medium'} onChange={(e) => updateChange(c.id, 'priority', e.target.value)}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                      <option value="critical">Critical</option>
                    </select>
                  )}

                  {c.type === 'task_duration_change' && (
                    <div className="flex-row">
                      <input type="number" min="1" placeholder="Duration" value={c.duration_value || ''} onChange={(e) => updateChange(c.id, 'duration_value', parseFloat(e.target.value))} />
                      <select value={c.duration_unit || 'minutes'} onChange={(e) => updateChange(c.id, 'duration_unit', e.target.value)}>
                        <option value="minutes">Minutes</option>
                        <option value="hours">Hours</option>
                      </select>
                    </div>
                  )}

                  {c.type === 'resource_availability_change' && (
                    <>
                      <input type="datetime-local" placeholder="Available From" value={c.available_from || ''} onChange={(e) => updateChange(c.id, 'available_from', e.target.value)} />
                      <input type="datetime-local" placeholder="Available Until" value={c.available_until || ''} onChange={(e) => updateChange(c.id, 'available_until', e.target.value)} />
                    </>
                  )}

                  {c.type === 'add_temporary_resource' && (
                    <>
                      <input type="text" placeholder="Name" value={c.name || ''} onChange={(e) => updateChange(c.id, 'name', e.target.value)} />
                      <input type="text" placeholder="Resource Type" value={c.resource_type || 'developer'} onChange={(e) => updateChange(c.id, 'resource_type', e.target.value)} />
                      <input type="number" min="1" placeholder="Capacity" value={c.capacity || 1} onChange={(e) => updateChange(c.id, 'capacity', parseInt(e.target.value))} />
                    </>
                  )}
                </div>
              ))}
              
              <div className="builder-actions">
                <button className="button secondary" onClick={() => addChange('resource_unavailable')}>+ Add Change</button>
              </div>

              {changes.length > 0 && (
                <div className="save-scenario-box">
                  <input type="text" id="scenario-name" placeholder="Scenario Name" />
                  <button className="button secondary" onClick={() => {
                    const name = document.getElementById('scenario-name').value;
                    handleSaveScenario(name);
                    document.getElementById('scenario-name').value = '';
                  }}>Save for Comparison</button>
                </div>
              )}
            </div>
            
            <button className="button primary full-width" onClick={handleRunSimulation} disabled={runningSim || changes.length === 0}>
              {runningSim ? "Simulating..." : "Run What-If"}
            </button>
            <button className="button outline full-width" style={{marginTop: '10px'}} onClick={() => {setChanges([]); setSimulationResult(null);}}>Reset</button>
          </div>
          
          <div className="simulation-results">
            {simulationResult ? (
              <div className="scenario-dashboard">
                <div className="impact-summary card">
                  <h3>Impact Summary</h3>
                  <div className="comparison-table-inline">
                    <table>
                      <thead>
                        <tr>
                          <th>Metric</th>
                          <th>Current</th>
                          <th>What-If</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr>
                          <td>Status</td>
                          <td>{baselineAnalysis?.status}</td>
                          <td>{simulationResult.scenario.status?.toUpperCase()}</td>
                        </tr>
                        <tr>
                          <td>Completion</td>
                          <td>{baselineRunDetail?.makespan ? new Date(baselineRunDetail.makespan).toLocaleTimeString() : 'N/A'}</td>
                          <td>{simulationResult.scenario.makespan ? new Date(simulationResult.scenario.makespan).toLocaleTimeString() : 'N/A'}</td>
                        </tr>
                        <tr>
                          <td>Health</td>
                          <td>{baselineAnalysis?.health?.score || 'N/A'}</td>
                          <td>{simulationResult.scenario.health?.score || 'N/A'}</td>
                        </tr>
                        <tr>
                          <td>Violations</td>
                          <td>{baselineAnalysis?.issues?.length || 0}</td>
                          <td>{simulationResult.scenario.issues?.length || 0}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  
                  <div className="impact-details">
                    <p><strong>Makespan:</strong> {simulationResult.impact.makespan_change_minutes > 0 ? '+' : ''}{simulationResult.impact.makespan_change_minutes} minutes</p>
                    <p><strong>Health:</strong> {simulationResult.impact.health_score_change > 0 ? '+' : ''}{simulationResult.impact.health_score_change}</p>
                    <p><strong>New Issues:</strong> {simulationResult.impact.new_issues_count}</p>
                    <p><strong>Resolved Issues:</strong> {simulationResult.impact.resolved_issues_count}</p>
                  </div>
                </div>
                
                <div className="scenario-schedule">
                  <h3>Scenario Schedule</h3>
                  {simulationResult.scenario.status?.toUpperCase() === 'INFEASIBLE' ? (
                    <InfeasibleView issues={simulationResult.scenario.issues || []} recoveryOptions={simulationResult.scenario.recovery_options || []} />
                  ) : (
                    <>
                      <StatusHeader status={simulationResult.scenario.status?.toUpperCase()} health={simulationResult.scenario.health} solverRuns={[]} />
                      <div className="results-grid">
                        <div className="results-main">
                          <GanttChart planId={planId} runDetail={simulationResult.scenario} />
                        </div>
                        <aside className="results-sidebar">
                          {simulationResult.scenario.health && <PlanHealth health={simulationResult.scenario.health} />}
                          <RisksAndBottlenecks risks={simulationResult.scenario.risks || []} bottlenecks={simulationResult.scenario.bottlenecks || []} />
                        </aside>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <Icon name="branch" size="large" />
                <h3>Baseline Plan</h3>
                {baselineAnalysis && (
                  <div className="baseline-metrics">
                    <p>Status: <strong>{baselineAnalysis.status}</strong></p>
                    <p>Completion: <strong>{baselineRunDetail?.makespan ? new Date(baselineRunDetail.makespan).toLocaleTimeString() : 'N/A'}</strong></p>
                    <p>Health: <strong>{baselineAnalysis.health?.score || 'N/A'} / 100</strong></p>
                    <p>Issues: <strong>{baselineAnalysis.issues?.length || 0}</strong></p>
                  </div>
                )}
                <p>Add changes to the left and run a simulation to see the impact.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'comparison' && (
        <div className="comparison-view">
          <div className="scenarios-sidebar">
            <h3>Saved Scenarios ({scenarios.length}/4)</h3>
            <ul className="scenarios-list">
              {scenarios.map((s, idx) => (
                <li key={idx} className="card">
                  <strong>{s.name}</strong>
                  <p className="text-small">{s.changes.length} change(s)</p>
                </li>
              ))}
            </ul>
            <button className="button primary" onClick={handleRunComparison} disabled={scenarios.length < 2 || scenarios.length > 4 || runningComp}>
              {runningComp ? "Comparing..." : "Compare Scenarios"}
            </button>
            <p className="text-small">Save 2-4 scenarios from the Simulator tab to compare them.</p>
          </div>
          
          <div className="comparison-results">
            {comparisonResult ? (
              <div className="card">
                <h3>Scenario Comparison</h3>
                <table className="comparison-table full-width">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Current</th>
                      {comparisonResult.scenarios.map((s, i) => <th key={i}>{s.name}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Status</td>
                      <td>{comparisonResult.baseline.status?.toUpperCase()}</td>
                      {comparisonResult.scenarios.map((s, i) => <td key={i}>{s.status?.toUpperCase()}</td>)}
                    </tr>
                    <tr>
                      <td>Makespan</td>
                      <td>{comparisonResult.baseline.makespan_minutes || 'N/A'} min</td>
                      {comparisonResult.scenarios.map((s, i) => <td key={i}>{s.makespan_minutes || 'N/A'} min</td>)}
                    </tr>
                    <tr>
                      <td>Health</td>
                      <td>{comparisonResult.baseline.health?.score || 'N/A'}</td>
                      {comparisonResult.scenarios.map((s, i) => <td key={i}>{s.health?.score || 'N/A'}</td>)}
                    </tr>
                    <tr>
                      <td>Violations</td>
                      <td>{comparisonResult.baseline.issues?.length || 0}</td>
                      {comparisonResult.scenarios.map((s, i) => <td key={i}>{s.issues?.length || 0}</td>)}
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <Icon name="history" size="large" />
                <h3>No Comparison Yet</h3>
                <p>Run a comparison to see metrics side by side.</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
