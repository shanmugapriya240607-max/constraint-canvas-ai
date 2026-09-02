import React from 'react';

const PIPELINE_STAGES = [
  { id: 1, title: 'User Text', desc: 'Natural language requirements' },
  { id: 2, title: 'ChatGPT Extraction', desc: 'Structured JSON parsing' },
  { id: 3, title: 'Pydantic Validation', desc: 'Schema & type verification' },
  { id: 4, title: 'Priority Engine', desc: 'DAG level & impact scoring' },
  { id: 5, title: 'OR-Tools Optimization', desc: 'CP-SAT constraint solver' },
  { id: 6, title: 'SQLite Storage', desc: 'Runs & history persistence' },
  { id: 7, title: 'Visual Schedule', desc: 'Table, Gantt & Timeline' },
];

export default function PipelineView() {
  return (
    <div className="section-card pipeline-view-card">
      <div className="section-card-header">
        <div>
          <h3>System Architecture &amp; Processing Pipeline</h3>
          <p className="section-card-desc">
            End-to-end constraint solving workflow from natural language to mathematical optimization
          </p>
        </div>
      </div>

      <div className="pipeline-flow-container">
        {PIPELINE_STAGES.map((stage, idx) => (
          <React.Fragment key={stage.id}>
            <div className="pipeline-flow-step">
              <div className="flow-step-number">{stage.id}</div>
              <div className="flow-step-content">
                <span className="flow-step-title">{stage.title}</span>
                <span className="flow-step-desc">{stage.desc}</span>
              </div>
            </div>
            {idx < PIPELINE_STAGES.length - 1 && (
              <div className="flow-arrow" aria-hidden="true">
                →
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
