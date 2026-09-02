import React from 'react';

const OFFICE_EXAMPLE = `Tomorrow I must reach the office by 9:00 AM. I want to start my morning routine as late as possible. Waking up takes 5 minutes. After waking up, I need to get ready for 30 minutes. After getting ready, I need to eat breakfast for 20 minutes. After breakfast, I need to travel to the office for 40 minutes. Travel must finish by 9:00 AM. These tasks must happen in that order.`;

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
        <button
          id="load-example-btn"
          type="button"
          className="btn btn-outline"
          disabled={loading}
          onClick={() => onLoadExample(OFFICE_EXAMPLE)}
          aria-label="Load Office Example text"
        >
          Load Office Example
        </button>
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
