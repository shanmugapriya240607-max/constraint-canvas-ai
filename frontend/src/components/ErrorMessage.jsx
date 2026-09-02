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

  // Case 4: Network, HTTP 400, 422, 502, 500 or Server Exception
  if (error || (result && (result.status === 'ERROR' || result.detail))) {
    let errorTitle = 'Service Error';
    let errorMsg = 'An unexpected communication error occurred. Please try again.';

    if (typeof error === 'string') {
      errorMsg = error;
    } else if (error && typeof error === 'object') {
      if (error.status === 400) {
        errorTitle = 'Invalid Input Request (HTTP 400)';
        errorMsg = error.message || 'Planning text is required.';
      } else if (error.status === 422) {
        errorTitle = 'Validation Request Error (HTTP 422)';
        errorMsg = error.message || 'Unprocessable planning payload.';
      } else if (error.status === 502) {
        errorTitle = 'AI Intelligence Gateway Error (HTTP 502)';
        errorMsg = error.message || 'The intelligence service is temporarily unavailable or returned invalid output.';
      } else if (error.status === 500) {
        errorTitle = 'Server Configuration Error (HTTP 500)';
        errorMsg = error.message || 'An unexpected server error occurred. Please check server logs.';
      } else if (error.message) {
        errorMsg = error.message;
      }
    } else if (result?.detail) {
      errorMsg = typeof result.detail === 'string' ? result.detail : 'Server error details.';
    }

    return (
      <div className="error-card error-border" aria-live="polite">
        <div className="error-card-header">
          <div className="error-icon danger-icon">!</div>
          <div>
            <h3 className="error-title danger-title">{errorTitle}</h3>
            <p className="error-subtitle">{errorMsg}</p>
          </div>
        </div>

        <div className="error-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onFocusTextarea}
          >
            Retry Input
          </button>
        </div>
      </div>
    );
  }

  return null;
}
