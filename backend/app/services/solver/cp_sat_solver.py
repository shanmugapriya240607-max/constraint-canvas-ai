"""Real CP-SAT model with non-preemptive tasks and capacity-unit allocation."""
from dataclasses import dataclass

from ortools.sat.python import cp_model
from app.services.solver.input_builder import SolverInput, SolverInputError
from app.services.solver.objective import attach_objective
from app.services.solver.result_builder import build_result


@dataclass
class ModelArtifacts:
    model: object
    starts: dict
    ends: dict
    units: dict
    present: dict
    objective: object


def build_model(data: SolverInput) -> ModelArtifacts:
    model = cp_model.CpModel()
    starts, ends, assignments = {}, {}, {}
    tasks = sorted(data.snapshot.tasks,key=lambda item:item.id)
    for task in tasks:
        start = model.new_int_var(0,data.horizon,f"start_{task.id}")
        end = model.new_int_var(0,data.horizon,f"end_{task.id}")
        model.new_interval_var(start,task.duration_minutes,end,f"task_{task.id}")
        starts[task.id],ends[task.id] = start,end
        model.add(start >= data.earliest[task.id])
        model.add(end <= data.deadlines[task.id])
    for before,after in data.dependencies:
        model.add(starts[after] >= ends[before])
    for task in tasks:
        for requirement in sorted(task.requirements,key=lambda item:item.id):
            variables = []
            for resource_id in data.candidates[requirement.id]:
                units = model.new_int_var(0,min(requirement.quantity,data.capacities[resource_id]),
                                          f"units_{task.id}_{requirement.id}_{resource_id}")
                variables.append(units)
                assignments.setdefault((task.id,resource_id),[]).append(units)
            model.add(sum(variables) == requirement.quantity)

    totals, present = {}, {}
    intervals, demands = {}, {}
    for task in tasks:
        for resource in sorted(data.snapshot.resources,key=lambda item:item.id):
            key = (task.id,resource.id)
            if key not in assignments:
                continue
            total = model.new_int_var(0,data.capacities[resource.id],f"total_{task.id}_{resource.id}")
            model.add(total == sum(assignments[key]))
            used = model.new_bool_var(f"uses_{task.id}_{resource.id}")
            model.add(total >= 1).only_enforce_if(used)
            model.add(total == 0).only_enforce_if(used.Not())
            interval = model.new_optional_interval_var(starts[task.id],task.duration_minutes,ends[task.id],
                                                       used,f"allocation_{task.id}_{resource.id}")
            totals[key],present[key] = total,used
            intervals.setdefault(resource.id,[]).append(interval)
            demands.setdefault(resource.id,[]).append(total)
            windows = []
            for index,(lower,upper) in enumerate(data.windows[resource.id]):
                if upper-lower < task.duration_minutes:
                    continue
                choice = model.new_bool_var(f"window_{task.id}_{resource.id}_{index}")
                model.add(starts[task.id] >= lower).only_enforce_if(choice)
                model.add(ends[task.id] <= upper).only_enforce_if(choice)
                windows.append(choice)
            # Exactly one whole window for each selected resource; no mid-task swapping.
            model.add(sum(windows) == used)
    for resource_id in sorted(intervals):
        model.add_cumulative(intervals[resource_id],demands[resource_id],data.capacities[resource_id])
    for resource_id,limit in data.max_work_minutes.items():
        work = sum(task.duration_minutes * totals.get((task.id,resource_id),0) for task in tasks)
        model.add(work <= limit)
    objective = attach_objective(model,data,ends,present)
    if model.validate():
        raise SolverInputError("The supplied planning data cannot form a valid bounded CP-SAT model")
    return ModelArtifacts(model,starts,ends,totals,present,objective)


def solve(data: SolverInput, max_solve_seconds: float):
    artifacts = build_model(data)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_solve_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.log_search_progress = False
    status = solver.solve(artifacts.model)
    if status == cp_model.MODEL_INVALID:
        raise SolverInputError("CP-SAT rejected the bounded model")
    return build_result(data,artifacts,solver,status)
