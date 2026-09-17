export default function WizardProgress({ steps, currentStep }) {
  return (
    <div className="wizard-progress">
      {steps.map((step, index) => (
        <div
          key={index}
          className={`wizard-step ${
            index === currentStep
              ? "active"
              : index < currentStep
                ? "completed"
                : ""
          }`}
        >
          <div className="step-circle">{index < currentStep ? "✓" : index + 1}</div>
          <div className="step-label">{step}</div>
        </div>
      ))}
    </div>
  );
}
