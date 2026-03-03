export default function StepIndicator({ step }) {
  return (
    <div className="step-indicator">
      <span className="dot" />
      {step}
    </div>
  );
}