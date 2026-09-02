import React from 'react';

export default function ErrorMessage({ result, error, onFocusTextarea }) {
  if (!result && !error) return null;

  // Case 1: Status NEEDS_INPUT
  if (result && result.status === 'NEEDS_INPUT') {
    const questions = result.questions || [];
    return (
      <div className="error-card warning-border" aria-live="polite">
        <div className="error-card-header">
          <div className="error-icon warning-icon">?</div>
          <div>
            <h3 className="error-title warning-title">
              More information is required before optimization.
            </h3>
            <p className="error-subtitle">
              {result.message || 'Please clarify the following missing details in your prompt.'}
            </p>
          </div>
        </div>

        {questions.length > 0 && (
          <ul className="question-list">
            {questions.map((q, idx) => (
              <li key={idx} className="question-item">
                <span className="question-bullet">•</span>
                <span>{q}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="error-actions">
          <button
            type="button"
            className="btn btn-outline"
            onClick={onFocusTextarea}
            aria-label="Focus requirement text input to edit"
          >
            Edit requirement
          </button>
        </div>
      </div>
    );
  }

  // Case 2: Status INVALID
  if (result && result.status === 'INVALID') {
    const errors = result.errors || [];
    return (
      <div className="error-card error-border" aria-live="polite">
        <div className="error-card-header">
          <div className="error-icon danger-icon">!</div>
          <div>
            <h3 className="error-title danger-title">
              The planning model contains invalid constraints.
            </h3>
            <p className="error-subtitle">
              {result.message || 'Please fix the constraint issues listed below.'}
            </p>
          </div>
        </div>

        {errors.length > 0 && (
          <div className="validation-error-list">
            {errors.map((errItem, idx) => (
              <div key={idx} className="validation-error-box">
                <div className="err-code-header font-mono">
                  CODE: {errItem.code || 'VALIDATION_ERROR'}
                </div>
                <p className="err-msg">{errItem.message}</p>
                {errItem.task_ids && errItem.task_ids.length > 0 && (
                  <div className="affected-tasks">
                    <strong>Affected Tasks:</strong> {errItem.task_ids.join(', ')}
                  </div>
                )}
                {errItem.suggestion && (
                  <div className="err-suggestion">
                    <strong>Suggested Correction:</strong> {errItem.suggestion}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="error-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onFocusTextarea}
          >
            Edit requirement
          </button>
        </div>
      </div>
    );
  }

  // Case 3: Status INFEASIBLE
  if (result && result.status === 'INFEASIBLE') {
    return (
      <div className="error-card error-border" aria-live="polite">
        <div className="error-card-header">
          <div className="error-icon danger-icon">✕</div>
          <div>
            <h3 className="error-title danger-title">
              No feasible schedule found — check your constraints.
            </h3>
            <p className="error-explanation">
              {result.explanation ||
                result.message ||
                'The required tasks cannot be completed within the stated deadline or resource limits.'}
            </p>
          </div>
        </div>

        <div className="error-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onFocusTextarea}
          >
            Adjust constraints
          </button>
        </div>
      </div>
    );
  }

  // Case 4: Network / Server error string or object
  if (error || (result && (result.status === 'ERROR' || result.detail))) {
    const errorMsg =
      typeof error === 'string'
        ? error
        : error?.message ||
          result?.detail ||
          result?.message ||
          'An unexpected communication error occurred. Please try again.';

    return (
      <div className="error-card error-border" aria-live="polite">
        <div className="error-card-header">
          <div className="error-icon danger-icon">!</div>
          <div>
            <h3 className="error-title danger-title">Service Error</h3>
            <p className="error-subtitle">{errorMsg}</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
