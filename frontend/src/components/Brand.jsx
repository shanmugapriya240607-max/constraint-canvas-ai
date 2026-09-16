import Icon from "./Icon";
export default function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark">
        <Icon name="layers" size={24} />
      </span>
      <span>
        ConstraintCanvas <small>AI</small>
      </span>
    </div>
  );
}
