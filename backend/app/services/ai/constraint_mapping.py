"""Explicit semantic adapters. Runtime custom types never become solver programs."""
from app.schemas.ai_parser import ConstraintPreview
from app.schemas.planning import ConstraintRuleCreate
from app.schemas.solver import (
    AvailabilityRule, CapacityRule, DeadlineRule, DependencyRule, MaxWorkRule,
    PreferredResourceRule, PreferredTimeRule,
)

HANDLERS = {
    "deadline": (DeadlineRule, "hard", {"before", "<="}),
    "dependency": (DependencyRule, "hard", {"before", "depends_on"}),
    "resource_capacity": (CapacityRule, "hard", {"=", "<="}),
    "availability": (AvailabilityRule, "hard", {"="}),
    "max_work_hours": (MaxWorkRule, "hard", {"<="}),
    "preferred_resource": (PreferredResourceRule, "soft", {"="}),
    "preferred_time": (PreferredTimeRule, "soft", {"before", "<="}),
}
TASK_REFS = {"task_id", "before_task_id", "after_task_id"}


def map_constraint(rule, index, task_ids, resource_ids):
    handler = HANDLERS.get(rule.semantic)
    supported = bool(handler and rule.hardness == handler[1] and rule.operator in handler[2])
    preview = ConstraintPreview(
        index=index, semantic=rule.semantic, solver_supported=supported,
        reason="Explicit supported handler" if supported else "No handler for this semantic/operator/hardness; stored disabled",
    )
    if not supported:
        return preview, ConstraintRuleCreate(
            constraint_type="custom", hardness=rule.hardness,
            weight=(rule.weight or 1) if rule.hardness == "soft" else rule.weight,
            source="ai", enabled=False, parameters=rule.model_dump(mode="json"),
        )
    parameters = dict(rule.parameters)
    for key in TASK_REFS | {"resource_id"}:
        if key in parameters:
            mapping = resource_ids if key == "resource_id" else task_ids
            reference = parameters[key]
            if not isinstance(reference, str) or reference not in mapping:
                raise ValueError("Constraint reference must be a client ID in this draft")
            parameters[key] = mapping[reference]
    validated = handler[0].model_validate(parameters)
    return preview, ConstraintRuleCreate(
        constraint_type=rule.semantic, hardness=rule.hardness, weight=(rule.weight or 1) if rule.hardness == "soft" else rule.weight,
        parameters=validated.model_dump(mode="json"), source="ai", enabled=True,
    )
