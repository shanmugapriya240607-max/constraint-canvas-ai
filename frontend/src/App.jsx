import React, { useState, useEffect, useRef } from 'react';
import { fetchHealth, solveProblem } from './api';
import ProblemInput from './components/ProblemInput';
import LoadingState from './components/LoadingState';
import ExtractedData from './components/ExtractedData';
import ResultTable from './components/ResultTable';
import GanttChart from './components/GanttChart';
import TaskTimeline from './components/TaskTimeline';
import ErrorMessage from './components/ErrorMessage';
import PipelineView from './components/PipelineView';
import RecentPlans from './components/RecentPlans';

export default function App() {
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [solveResult, setSolveResult] = useState(null);
  const [error, setError] = useState(null);
  const [historyTrigger, setHistoryTrigger] = useState(0);

  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const textareaRef = useRef(null);

  // Poll / Check health status on mount
  useEffect(() => {
    let isMounted = true;
    fetchHealth()
      .then((data) => {
        if (isMounted) {
          setHealthStatus(data);
          setHealthLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setHealthStatus({ status: 'offline', database: 'disconnected', optimizer: 'unavailable' });
          setHealthLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleFocusTextarea = () => {
    if (textareaRef.current) {
      textareaRef.current.focus();
      textareaRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleClear = () => {
    setInputText('');
    setSolveResult(null);
    setError(null);
  };

  const handleLoadExample = (exampleText) => {
    setInputText(exampleText);
    setError(null);
  };

  const handleSelectHistoryRun = (savedResult, originalText) => {
    setSolveResult(savedResult);
    if (originalText) {
      setInputText(originalText);
    }
    setError(null);
    // Smooth scroll to results
    const el = document.getElementById('results-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const handleAnalyze = async () => {
    if (!inputText || !inputText.trim() || loading) return;

    setLoading(true);
    setLoadingStep(0);
    setError(null);

    // Simulate step progress while waiting for backend
    const stepInterval = setInterval(() => {
      setLoadingStep((prev) => (prev < 4 ? prev + 1 : prev));
    }, 600);

    try {
      const data = await solveProblem(inputText);
      setSolveResult(data);
      // Trigger history list refresh after successful solve
      setHistoryTrigger((prev) => prev + 1);
    } catch (err) {
      console.error('Analysis failed:', err);
      setSolveResult(null);
      setError(err);
    } finally {
      clearInterval(stepInterval);
      setLoading(false);
    }
  };

  const isSuccessResult =
    solveResult && (solveResult.status === 'OPTIMAL' || solveResult.status === 'FEASIBLE');

  // Fallback deterministic explanation if backend explanation is absent
  let explanationText = solveResult?.explanation;
  if (!explanationText && isSuccessResult && solveResult.tasks?.length > 0) {
    const sorted = [...solveResult.tasks].sort((a, b) => (a.start || '').localeCompare(b.start || ''));
    const firstStart = sorted[0]?.start || '00:00';
    const lastEnd = sorted[sorted.length - 1]?.end || '23:59';
    explanationText = `The schedule starts at ${firstStart} and completes by ${lastEnd}. All ${solveResult.tasks.length} tasks satisfy their dependencies and deadline.`;
  }

  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-title">
          <h1>
            ConstraintCanvas <span className="logo-accent">AI</span>
          </h1>
          <p>Natural-Language Planning and Optimization Engine</p>
        </div>

        <div className="status-bar" aria-label="System status indicators">
          <div className="status-badge" title="ChatGPT Extraction Status">
            <span
              className={`status-dot ${
                healthStatus?.openai_configured ? 'active' : 'inactive'
              }`}
            ></span>
            <span>ChatGPT</span>
          </div>

          <div className="status-badge" title="Pydantic Validation Engine Status">
            <span
              className={`status-dot ${
                healthStatus?.status === 'healthy' ? 'active' : 'offline'
              }`}
            ></span>
            <span>Pydantic</span>
          </div>

          <div className="status-badge" title="OR-Tools Solver Engine Status">
            <span
              className={`status-dot ${
                healthStatus?.optimizer === 'available' ? 'active' : 'offline'
              }`}
            ></span>
            <span>OR-Tools</span>
          </div>

          <div className="status-badge" title="SQLite Database Persistence Status">
            <span
              className={`status-dot ${
                healthStatus?.database === 'connected' ? 'active' : 'offline'
              }`}
            ></span>
            <span>SQLite</span>
          </div>
        </div>
      </header>

      {/* Processing Pipeline Architecture View */}
      <PipelineView />

      {/* Main Problem Input Section */}
      <ProblemInput
        value={inputText}
        onChange={setInputText}
        onAnalyze={handleAnalyze}
        onClear={handleClear}
        onLoadExample={handleLoadExample}
        loading={loading}
        textareaRef={textareaRef}
      />

      {/* Loading Spinner & Pipeline */}
      {loading && <LoadingState currentStep={loadingStep} />}

      {/* Error & Non-Optimal Status Messages */}
      {!loading && (
        <ErrorMessage
          result={solveResult}
          error={error}
          onFocusTextarea={handleFocusTextarea}
        />
      )}

      {/* Result Display Section (Only for OPTIMAL and FEASIBLE) */}
      {!loading && isSuccessResult && (
        <div className="results-container" id="results-section">
          {/* Explanation Banner */}
          {explanationText && (
            <div className="explanation-banner">
              <span className="explanation-icon">💡</span>
              <p className="explanation-text">{explanationText}</p>
            </div>
          )}

          {/* Extracted Metrics Summary */}
          <ExtractedData result={solveResult} />

          {/* Dynamic Gantt Chart */}
          <GanttChart tasks={solveResult.tasks} />

          {/* Schedule Table */}
          <ResultTable tasks={solveResult.tasks} />

          {/* Task Execution Timeline */}
          <TaskTimeline tasks={solveResult.tasks} />
        </div>
      )}

      {/* Recent Plans (SQLite History) */}
      <RecentPlans
        onSelectRun={handleSelectHistoryRun}
        refreshTrigger={historyTrigger}
      />

      {/* Footer */}
      <footer className="app-footer">
        <p>ConstraintCanvas AI — Full-Stack Natural Language Planning &amp; CP-SAT Optimization Prototype</p>
      </footer>
    </div>
  );
}
