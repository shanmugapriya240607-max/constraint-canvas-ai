import { useState } from "react";
import WizardProgress from "../components/planner/WizardProgress";
import WizardNavigation from "../components/planner/WizardNavigation";
import PlanDetailsStep from "../components/planner/PlanDetailsStep";
import ResourcesStep from "../components/planner/ResourcesStep";
import AvailabilityStep from "../components/planner/AvailabilityStep";
import TasksStep from "../components/planner/TasksStep";
import RequirementsStep from "../components/planner/RequirementsStep";
import DependenciesStep from "../components/planner/DependenciesStep";
import ConstraintsStep from "../components/planner/ConstraintsStep";
import ReviewStep from "../components/planner/ReviewStep";
import SuccessScreen from "../components/planner/SuccessScreen";
import { submitFullPlan } from "../services/planner";

const STEPS = [
  "Details",
  "Resources",
  "Availability",
  "Tasks",
  "Requirements",
  "Dependencies",
  "Constraints",
  "Review",
];

export default function CreatePlan() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isNextDisabled, setIsNextDisabled] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [successData, setSuccessData] = useState(null);

  const [wizardState, setWizardState] = useState({
    planDetails: {
      name: "",
      description: "",
      planningStart: "",
      planningEnd: "",
    },
    resources: [],
    availabilities: [],
    tasks: [],
    requirements: [],
    dependencies: [],
    constraints: [],
  });

  const updateState = (key, data) => {
    setWizardState((prev) => ({ ...prev, [key]: data }));
  };

  const handleNext = async () => {
    console.log("handleNext called, currentStep:", currentStep);
    if (currentStep < STEPS.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      // Submit the plan
      console.log("Submitting full plan...");
      setIsSubmitting(true);
      setSubmitError(null);
      try {
        const result = await submitFullPlan(wizardState);
        console.log("Submit success:", result);
        setSuccessData(result);
      } catch (err) {
        console.error("Submit error:", err);
        setSubmitError(err.message || "An error occurred while creating the plan. Please try again.");
      } finally {
        console.log("Setting isSubmitting to false");
        setIsSubmitting(false);
      }
    }
  };

  const handleBack = () => {
    setCurrentStep((prev) => prev - 1);
    setSubmitError(null);
  };

  if (successData) {
    return (
      <div className="create-plan-container">
        <SuccessScreen planId={successData.planId} counts={successData.counts} />
      </div>
    );
  }

  return (
    <div className="create-plan-container">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PLANNING WIZARD</span>
          <h1>Create New Plan</h1>
        </div>
      </div>

      <WizardProgress steps={STEPS} currentStep={currentStep} />

      {submitError && (
        <div className="notice error" role="alert">
          {submitError}
        </div>
      )}

      <div className="wizard-content-area">
        {currentStep === 0 && (
          <PlanDetailsStep
            data={wizardState.planDetails}
            onChange={(d) => updateState("planDetails", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 1 && (
          <ResourcesStep
            data={wizardState.resources}
            onChange={(d) => updateState("resources", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 2 && (
          <AvailabilityStep
            data={wizardState.availabilities}
            resources={wizardState.resources}
            onChange={(d) => updateState("availabilities", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 3 && (
          <TasksStep
            data={wizardState.tasks}
            onChange={(d) => updateState("tasks", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 4 && (
          <RequirementsStep
            data={wizardState.requirements}
            tasks={wizardState.tasks}
            resources={wizardState.resources}
            onChange={(d) => updateState("requirements", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 5 && (
          <DependenciesStep
            data={wizardState.dependencies}
            tasks={wizardState.tasks}
            onChange={(d) => updateState("dependencies", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 6 && (
          <ConstraintsStep
            data={wizardState.constraints}
            tasks={wizardState.tasks}
            resources={wizardState.resources}
            onChange={(d) => updateState("constraints", d)}
            onValidationChange={(isValid) => setIsNextDisabled(!isValid)}
          />
        )}
        {currentStep === 7 && (
          <ReviewStep
            wizardState={wizardState}
            onEditStep={(step) => {
              setCurrentStep(step);
              setSubmitError(null);
            }}
          />
        )}
      </div>

      <WizardNavigation
        currentStep={currentStep}
        totalSteps={STEPS.length}
        onNext={handleNext}
        onBack={handleBack}
        isNextDisabled={currentStep !== STEPS.length - 1 && isNextDisabled}
        isSubmitting={isSubmitting}
      />
    </div>
  );
}
