import Icon from "../Icon";

export default function WizardNavigation({
  currentStep,
  totalSteps,
  onNext,
  onBack,
  isNextDisabled = false,
  isSubmitting = false,
}) {
  return (
    <div className="wizard-navigation">
      <button
        type="button"
        className="button secondary"
        onClick={onBack}
        disabled={currentStep === 0 || isSubmitting}
      >
        <Icon name="arrow-left" size={16} /> Back
      </button>

      {currentStep < totalSteps - 1 ? (
        <button
          type="button"
          className="button primary"
          onClick={onNext}
          disabled={isNextDisabled || isSubmitting}
        >
          Next <Icon name="arrow-right" size={16} />
        </button>
      ) : (
        <button
          type="button"
          className="button primary"
          onClick={onNext}
          disabled={isNextDisabled || isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Icon name="loader" size={16} className="spin" /> Creating Plan...
            </>
          ) : (
            <>
              <Icon name="check" size={16} /> Create Plan
            </>
          )}
        </button>
      )}
    </div>
  );
}
