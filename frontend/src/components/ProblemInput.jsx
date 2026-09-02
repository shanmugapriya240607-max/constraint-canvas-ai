import React from 'react';

const OFFICE_EXAMPLE = `Tomorrow I must reach the office by 9:00 AM. Waking up takes 10 minutes, getting ready takes 30 minutes, eating breakfast takes 20 minutes, and travelling to the office takes 40 minutes. Waking up must finish before getting ready, getting ready must finish before breakfast, and breakfast must finish before travelling to the office.`;

const STUDY_EXAMPLE = `I must submit my assignment before 6:00 PM. Research takes 45 minutes, writing takes 90 minutes, proofreading takes 20 minutes, and submission takes 5 minutes. Research must finish before writing, writing must finish before proofreading, and proofreading must finish before submission.`;

export default function ProblemInput({
  value,
  onChange,
  onAnalyze,
  onClear,
  onLoadExample,
  loading,
  textareaRef,
}) {
  const isInputEmpty = !value || !value.trim();

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !isInputEmpty && !loading) {
      e.preventDefault();
      onAnalyze();
    }
  };

  return (
    <div className="input-card" id="problem-input-section">
      <div className="card-header">
        <label htmlFor="planning-text-input" className="card-title-label">
          <h2>Enter Planning Requirement</h2>
        </label>
        <span className="shortcut-hint">Ctrl + Enter to analyze</span>
      </div>

      <div className="textarea-wrapper">
        <textarea
          id="planning-text-input"
          ref={textareaRef}
          className="problem-textarea"
          placeholder="Describe your schedule, deadlines, and dependencies in natural language..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={6}
          maxLength={4000}
          disabled={loading}
          aria-label="Planning requirement text"
        />
        <div className="textarea-footer">
          <span>Describe timing constraints, deadlines, resources, and dependencies.</span>
          <span className="char-counter">{value ? value.length : 0} / 4000 characters</span>
        </div>
      </div>

      <div className="button-group">
        <button
          id="analyze-btn"
          type="button"
          className="btn btn-primary"
          disabled={isInputEmpty || loading}
          onClick={onAnalyze}
          aria-label="Analyze and optimize schedule"
        >
          {loading ? 'Processing...' : 'Analyze & Optimize'}
        </button>

        <div className="example-buttons-group">
          <button
            id="load-office-example-btn"
            type="button"
            className="btn btn-outline"
            disabled={loading}
            onClick={() => onLoadExample(OFFICE_EXAMPLE)}
            aria-label="Load Office Routine Example"
          >
            Office Example
          </button>

          <button
            id="load-study-example-btn"
            type="button"
            className="btn btn-outline"
            disabled={loading}
            onClick={() => onLoadExample(STUDY_EXAMPLE)}
            aria-label="Load Evening Study Session Example"
          >
            Study Session Example
          </button>
        </div>

        <button
          id="clear-btn"
          type="button"
          className="btn btn-secondary"
          disabled={!value || loading}
          onClick={onClear}
          aria-label="Clear input text"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
