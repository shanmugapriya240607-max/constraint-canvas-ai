import re
from typing import List, Dict, Set
from app.schemas import ExtractedProblem, Task, ValidationResult, ValidationErrorDetail

TIME_24H_REGEX = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")


def hhmm_to_minutes(hhmm: str) -> int:
    """Converts 24-hour HH:MM string to minutes from midnight (0..1439). Raises ValueError on invalid format or range."""
    if not isinstance(hhmm, str) or not TIME_24H_REGEX.match(hhmm.strip()):
        raise ValueError(f"Invalid time format: '{hhmm}'. Expected 24-hour HH:MM format (00:00 to 23:59).")
    
    parts = hhmm.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])

    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError(f"Time out of bounds: '{hhmm}'.")

    total = hours * 60 + minutes
    if total < 0 or total > 1439:
        raise ValueError(f"Minutes out of 24-hour horizon range [0..1439]: {total}")
    return total


def minutes_to_hhmm(minutes: int) -> str:
    """Converts minutes from midnight (0..1439) to 24-hour HH:MM string with leading zeros."""
    if not isinstance(minutes, int) or minutes < 0 or minutes > 1439:
        raise ValueError(f"Minutes value must be an integer between 0 and 1439. Got: {minutes}")
    
    hours = (minutes // 60) % 24
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def detect_circular_dependencies(tasks: List[Task]) -> List[str]:
    """
    Detects circular dependencies using Depth-First Search (DFS) graph traversal.
    Returns list of task IDs involved in a cycle, or empty list if acyclic.
    """
    task_map: Dict[str, Task] = {t.id: t for t in tasks}
    visited: Dict[str, int] = {t.id: 0 for t in tasks}  # 0: unvisited, 1: visiting, 2: visited
    cycle_nodes: Set[str] = set()

    def dfs(node_id: str, path: List[str]) -> bool:
        visited[node_id] = 1  # Mark visiting
        path.append(node_id)

        task = task_map.get(node_id)
        if task:
            for dep in task.depends_on:
                if dep in task_map:
                    if visited[dep] == 1:
                        # Cycle detected
                        cycle_start_index = path.index(dep)
                        cycle_nodes.update(path[cycle_start_index:])
                        return True
                    elif visited[dep] == 0:
                        if dfs(dep, path):
                            return True

        path.pop()
        visited[node_id] = 2  # Mark visited
        return False

    for task in tasks:
        if visited[task.id] == 0:
            dfs(task.id, [])

    return sorted(list(cycle_nodes))


def validate_extracted_problem(problem: ExtractedProblem) -> ValidationResult:
    errors: List[ValidationErrorDetail] = []
    warnings: List[str] = []

    # 1. Check empty task list
    if not problem.tasks:
        errors.append(ValidationErrorDetail(
            code="EMPTY_TASK_LIST",
            message="Task list cannot be empty.",
            suggestion="Provide at least one valid task."
        ))

    # 2. Check task uniqueness, names, durations, and time formats
    seen_ids: Set[str] = set()
    task_map: Dict[str, Task] = {}

    for task in problem.tasks:
        if task.id in seen_ids:
            errors.append(ValidationErrorDetail(
                code="DUPLICATE_TASK_ID",
                message=f"Duplicate task ID found: '{task.id}'.",
                task_ids=[task.id],
                suggestion="Ensure all task IDs are unique."
            ))
        seen_ids.add(task.id)
        task_map[task.id] = task

        if not task.name or not task.name.strip():
            errors.append(ValidationErrorDetail(
                code="EMPTY_TASK_NAME",
                message=f"Task '{task.id}' has an empty name.",
                task_ids=[task.id]
            ))

        if task.duration_minutes is None:
            errors.append(ValidationErrorDetail(
                code="MISSING_DURATION",
                message=f"Task '{task.name}' ({task.id}) is missing a duration.",
                task_ids=[task.id],
                suggestion="Specify duration in minutes."
            ))
        elif task.duration_minutes <= 0:
            errors.append(ValidationErrorDetail(
                code="INVALID_DURATION",
                message=f"Task '{task.name}' duration must be positive. Got: {task.duration_minutes}.",
                task_ids=[task.id]
            ))

        if task.earliest_start:
            try:
                hhmm_to_minutes(task.earliest_start)
            except ValueError as e:
                errors.append(ValidationErrorDetail(
                    code="INVALID_TIME_FORMAT",
                    message=f"Task '{task.name}' earliest_start format error: {str(e)}",
                    task_ids=[task.id]
                ))

        if task.deadline:
            try:
                hhmm_to_minutes(task.deadline)
            except ValueError as e:
                errors.append(ValidationErrorDetail(
                    code="INVALID_TIME_FORMAT",
                    message=f"Task '{task.name}' deadline format error: {str(e)}",
                    task_ids=[task.id]
                ))

        if task.earliest_start and task.deadline:
            try:
                es_min = hhmm_to_minutes(task.earliest_start)
                dl_min = hhmm_to_minutes(task.deadline)
                if es_min > dl_min:
                    errors.append(ValidationErrorDetail(
                        code="EARLIEST_START_AFTER_DEADLINE",
                        message=f"Task '{task.name}' earliest_start ({task.earliest_start}) is after its deadline ({task.deadline}).",
                        task_ids=[task.id],
                        suggestion="Adjust earliest start or deadline so start <= deadline."
                    ))
            except ValueError:
                pass  # Already logged invalid time format error above

    # 3. Check dependencies
    for task in problem.tasks:
        for dep_id in task.depends_on:
            if dep_id == task.id:
                errors.append(ValidationErrorDetail(
                    code="SELF_DEPENDENCY",
                    message=f"Task '{task.name}' ({task.id}) cannot depend on itself.",
                    task_ids=[task.id],
                    suggestion="Remove self-referencing dependency."
                ))
            elif dep_id not in task_map:
                errors.append(ValidationErrorDetail(
                    code="UNKNOWN_DEPENDENCY",
                    message=f"Task '{task.name}' ({task.id}) references unknown dependency task ID '{dep_id}'.",
                    task_ids=[task.id, dep_id],
                    suggestion="Verify dependency task ID matches an existing task."
                ))

    # 4. Check circular dependencies
    cycle_task_ids = detect_circular_dependencies(problem.tasks)
    if cycle_task_ids:
        errors.append(ValidationErrorDetail(
            code="CIRCULAR_DEPENDENCY",
            message="A circular dependency was detected.",
            task_ids=cycle_task_ids,
            suggestion="Remove one of the circular dependencies."
        ))

    # 5. Check objective
    allowed_objectives = {"MINIMIZE_MAKESPAN", "EARLIEST_FINISH", "LATEST_START"}
    if problem.objective and problem.objective.type not in allowed_objectives:
        errors.append(ValidationErrorDetail(
            code="UNSUPPORTED_OBJECTIVE",
            message=f"Objective type '{problem.objective.type}' is not supported.",
            suggestion=f"Use one of {allowed_objectives}."
        ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )
