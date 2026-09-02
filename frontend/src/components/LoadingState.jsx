import React from 'react';

const PIPELINE_STEPS = [
  'Understanding requirements',
  'Validating constraints',
  'Calculating priority',
  'Optimizing schedule',
  'Saving result',
];

export default function LoadingState({ currentStep = 0 }) {
  return (
    <div className="loading-card" aria-live="polite" aria-label="Loading optimization status">
      <div className="spinner-wrapper">
        <div className="spinner"></div>
      </div>
      <div className="loading-content">
        <h3>Analyzing Planning Requirement</h3>
        <p className="loading-subtitle">
          Converting natural language into an optimized schedule...
        </p>

        <div className="pipeline-steps">
          {PIPELINE_STEPS.map((step, idx) => {
            const isCompleted = idx < currentStep;
            const isCurrent = idx === currentStep;

            return (
              <div
                key={step}
                className={`pipeline-step ${isCompleted ? 'completed' : ''} ${
                  isCurrent ? 'active' : ''
                }`}
              >
                <span className="step-dot"></span>
                <span className="step-text">{step}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
