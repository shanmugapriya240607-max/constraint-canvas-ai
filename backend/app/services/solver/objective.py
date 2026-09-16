"""Integer objective: makespan first, then priority completion and soft penalties."""
from dataclasses import dataclass
from app.services.solver.input_builder import PRIORITY, SolverInputError, minute_offset


@dataclass
class ObjectiveTerms:
    makespan: object
    priority_completion: object
    soft_penalty: object
    secondary_upper_bound: int


def attach_objective(model, data, ends, present):
    horizon = data.horizon
    makespan = model.new_int_var(0,horizon,"makespan")
    model.add_max_equality(makespan,list(ends.values()))
    priority_completion = sum(PRIORITY[task.priority] * ends[task.id] for task in data.snapshot.tasks)
    upper = 1000 * horizon * sum(PRIORITY[task.priority] for task in data.snapshot.tasks)
    penalties = []
    for index,(kind,params,weight) in enumerate(data.preferences):
        if kind == "preferred_resource":
            use = present.get((params.task_id,params.resource_id),0)
            penalties.append(weight * (1-use))
            upper += weight
        else:
            target = max(0,min(horizon,minute_offset(params.preferred_before,data.snapshot.plan.planning_start)))
            late = model.new_int_var(0,horizon,f"soft_lateness_{index}")
            model.add_max_equality(late,[0,ends[params.task_id]-target])
            penalties.append(weight * late)
            upper += weight * horizon
    # This upper bound guarantees lexicographic dominance without arbitrary huge weights.
    if horizon * (upper+1) + upper >= 2**60:
        raise SolverInputError("Objective exceeds safe integer limits; reduce horizon or soft weights")
    soft_penalty = sum(penalties)
    model.minimize((upper+1)*makespan + 1000*priority_completion + soft_penalty)
    return ObjectiveTerms(makespan,priority_completion,soft_penalty,upper)
