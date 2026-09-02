import React, { useState, useEffect } from 'react';
import { fetchHealth } from './api';

const OFFICE_EXAMPLE = `Tomorrow I must reach the office by 9:00 AM. I want to start my morning routine as late as possible. Waking up takes 5 minutes. After waking up, I need to get ready for 30 minutes. After getting ready, I need to eat breakfast for 20 minutes. After breakfast, I need to travel to the office for 40 minutes. Travel must finish by 9:00 AM. These tasks must happen in that order.`;

export default function App() {
  const [inputText, setInputText] = useState('');
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState(null);

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
          setHealthError(err.message || 'Unable to connect to backend');
          setHealthLoading(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const handleClear = () => {
    setInputText('');
  };

  const handleLoadExample = () => {
    setInputText(OFFICE_EXAMPLE);
  };

  const handleAnalyze = () => {
    if (!inputText.trim()) return;
    alert("Phase 1 Base Setup active! Backend API is healthy. OpenAI & Solver engines will be enabled in Phase 2.");
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-title">
          <h1>
            ConstraintCanvas <span className="logo-accent">AI</span>
          </h1>
          <p>Natural-Language Planning and Optimization</p>
        </div>

        <div className="status-bar">
          <div className="status-badge" title="ChatGPT Integration Status">
            <span
              className={`status-dot ${
                healthStatus?.openai_configured ? 'active' : 'inactive'
              }`}
            ></span>
            <span>ChatGPT</span>
          </div>

          <div className="status-badge" title="Validation Engine Status">
            <span
              className={`status-dot ${
                healthStatus?.status === 'healthy' ? 'active' : 'offline'
              }`}
            ></span>
            <span>Validation</span>
          </div>

          <div className="status-badge" title="OR-Tools Solver Status">
            <span
              className={`status-dot ${
                healthStatus?.optimizer === 'available' ? 'active' : 'offline'
              }`}
            ></span>
            <span>OR-Tools</span>
          </div>
        </div>
      </header>

      <main className="input-card">
        <div className="card-header">
          <h2>Enter Planning Requirement</h2>
          {healthLoading ? (
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Checking API connection...
            </span>
          ) : healthError ? (
            <span style={{ fontSize: '0.85rem', color: 'var(--error)' }}>
              Backend offline ({healthError})
            </span>
          ) : (
            <span style={{ fontSize: '0.85rem', color: 'var(--success)' }}>
              API Connected ({healthStatus?.status})
            </span>
          )}
        </div>

        <div className="textarea-wrapper">
          <textarea
            id="planning-text-input"
            className="problem-textarea"
            placeholder="Describe your schedule, deadlines, and dependencies in natural language..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            rows={6}
          ></textarea>
          <div className="textarea-footer">
            <span>Describe timing constraints, deadlines, and dependencies.</span>
            <span>{inputText.length} characters</span>
          </div>
        </div>

        <div className="button-group">
          <button
            id="analyze-btn"
            className="btn btn-primary"
            disabled={!inputText.trim()}
            onClick={handleAnalyze}
          >
            Analyze &amp; Optimize
          </button>
          <button
            id="load-example-btn"
            className="btn btn-outline"
            onClick={handleLoadExample}
          >
            Load Office Example
          </button>
          <button
            id="clear-btn"
            className="btn btn-secondary"
            disabled={!inputText}
            onClick={handleClear}
          >
            Clear
          </button>
        </div>
      </main>

      <section className="phase-info-panel">
        <h3>Phase 1 System Ready</h3>
        <p>
          Base frontend layout and backend infrastructure loaded successfully. CORS is enabled for <code>http://localhost:5173</code> and <code>GET /api/health</code> is online.
        </p>
      </section>

      <footer className="app-footer">
        <p>ConstraintCanvas AI — Base Infrastructure Initialized</p>
      </footer>
    </div>
  );
}
