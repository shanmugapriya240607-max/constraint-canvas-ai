"""Only read schedule values when CP-SAT actually found a solution."""
from datetime import timedelta
from ortools.sat.python import cp_model

from app.schemas.solver import AssignedResource, ScheduledTask, SolveMetrics, SolveObjective, SolveResponse


def build_result(data, artifacts, solver, status):
    statuses = {cp_model.OPTIMAL:"optimal",cp_model.FEASIBLE:"feasible",cp_model.INFEASIBLE:"infeasible"}
    result_status = statuses.get(status,"unknown")
    warnings = list(data.warnings)
    schedule = []
    objective = None
    makespan = None
    if result_status in ("optimal","feasible"):
        resources = {resource.id:resource for resource in data.snapshot.resources}
        for task in sorted(data.snapshot.tasks,key=lambda item:item.id):
            start,end = solver.value(artifacts.starts[task.id]),solver.value(artifacts.ends[task.id])
            assignments = []
            for (task_id,resource_id),variable in sorted(artifacts.units.items()):
                if task_id == task.id and (units := solver.value(variable)) > 0:
                    resource = resources[resource_id]
                    assignments.append(AssignedResource(resource_id=resource_id,name=resource.name,
                        resource_type=resource.resource_type,units=units))
            schedule.append(ScheduledTask(
                task_id=task.id,task_name=task.name,start_offset_minutes=start,end_offset_minutes=end,
                start_time=data.snapshot.plan.planning_start+timedelta(minutes=start),
                end_time=data.snapshot.plan.planning_start+timedelta(minutes=end),
                duration_minutes=task.duration_minutes,priority=task.priority,assigned_resources=assignments,
            ))
        schedule.sort(key=lambda item:(item.start_offset_minutes,item.task_id))
        makespan = solver.value(artifacts.objective.makespan)
        objective = SolveObjective(makespan_minutes=makespan,
            weighted_priority_completion=solver.value(artifacts.objective.priority_completion),
            soft_penalty_scaled=solver.value(artifacts.objective.soft_penalty))
        if result_status == "feasible":
            warnings.append("A valid schedule was found; optimality was not proven within the solve limit")
    elif result_status == "unknown":
        warnings.append("Solve limit reached without a solution or infeasibility proof; feasibility is unknown")
    return SolveResponse(status=result_status,plan_id=data.snapshot.plan.id,objective=objective,schedule=schedule,
        metrics=SolveMetrics(task_count=len(data.snapshot.tasks),scheduled_task_count=len(schedule),
            planning_horizon_minutes=data.horizon,makespan_minutes=makespan,
            solver_wall_time_ms=round(solver.wall_time*1000,3)),warnings=warnings)
