from typing import List, Dict, Set, Tuple
from app.schemas import Task
from app.validator import hhmm_to_minutes


def calculate_task_priorities(tasks: List[Task]) -> List[Task]:
    """
    Computes topological execution level, downstream dependency impact,
    deadline urgency, critical path status, priority score (0..100), and priority reason.
    Returns copy of tasks with priority fields populated and ordered by level then priority.
    """
    if not tasks:
        return []

    task_map: Dict[str, Task] = {t.id: t for t in tasks}

    # 1. Build adjacency maps
    # predecessors: task_id -> set of dependency task_ids (tasks that MUST run BEFORE task_id)
    # successors: task_id -> set of task_ids that DEPEND ON task_id
    predecessors: Dict[str, Set[str]] = {t.id: set(t.depends_on) for t in tasks}
    successors: Dict[str, Set[str]] = {t.id: set() for t in tasks}

    for t in tasks:
        for dep in t.depends_on:
            if dep in successors:
                successors[dep].add(t.id)

    # 2. Execution Level (Topological distance from root)
    # Level 1 for root tasks (predecessors is empty), Level max(pred_levels) + 1 for others
    execution_levels: Dict[str, int] = {}
    
    def get_level(node_id: str, visited_nodes: Set[str]) -> int:
        if node_id in execution_levels:
            return execution_levels[node_id]
        if not predecessors[node_id]:
            execution_levels[node_id] = 1
            return 1
        
        visited_nodes.add(node_id)
        max_pred_level = 0
        for pred in predecessors[node_id]:
            if pred in task_map and pred not in visited_nodes:
                p_level = get_level(pred, visited_nodes.copy())
                if p_level > max_pred_level:
                    max_pred_level = p_level
        
        level = max_pred_level + 1 if max_pred_level > 0 else 1
        execution_levels[node_id] = level
        return level

    for t in tasks:
        get_level(t.id, set())

    # 3. Downstream impact count (total direct + indirect dependent tasks)
    downstream_counts: Dict[str, int] = {}
    
    def get_downstream_set(node_id: str) -> Set[str]:
        downstream: Set[str] = set()
        for succ in successors[node_id]:
            downstream.add(succ)
            downstream.update(get_downstream_set(succ))
        return downstream

    for t in tasks:
        downstream_counts[t.id] = len(get_downstream_set(t.id))

    max_downstream = max(downstream_counts.values()) if downstream_counts else 1

    # 4. Critical path calculation (longest duration path through DAG)
    longest_path_to_end: Dict[str, int] = {}

    def get_max_path_to_end(node_id: str) -> int:
        if node_id in longest_path_to_end:
            return longest_path_to_end[node_id]
        dur = task_map[node_id].duration_minutes or 0
        if not successors[node_id]:
            longest_path_to_end[node_id] = dur
            return dur
        max_succ_path = max(get_max_path_to_end(succ) for succ in successors[node_id])
        longest_path_to_end[node_id] = dur + max_succ_path
        return dur + max_succ_path

    for t in tasks:
        get_max_path_to_end(t.id)

    max_path_length = max(longest_path_to_end.values()) if longest_path_to_end else 1

    # Critical path nodes: nodes on path matching max_path_length
    critical_nodes: Set[str] = set()
    for t in tasks:
        # Check if node is part of the max length path
        # A node is critical if its distance from root + distance to end == max_path_length
        if max_path_length > 0 and longest_path_to_end[t.id] == max_path_length and not predecessors[t.id]:
            curr = t.id
            critical_nodes.add(curr)
            while successors[curr]:
                next_node = max(successors[curr], key=lambda s: longest_path_to_end[s])
                critical_nodes.add(next_node)
                curr = next_node

    # If any task has explicit deadline urgency
    urgency_scores: Dict[str, float] = {}
    for t in tasks:
        if t.deadline:
            try:
                dl_min = hhmm_to_minutes(t.deadline)
                # Earlier deadline = higher urgency score (normalized to 100)
                urgency = max(0.0, min(100.0, (1440.0 - dl_min) / 1440.0 * 100.0))
            except ValueError:
                urgency = 0.0
        else:
            urgency = 0.0
        urgency_scores[t.id] = urgency

    max_urgency = max(urgency_scores.values()) if any(urgency_scores.values()) else 1.0

    # 5. Calculate Priority Score & Build Task Objects
    updated_tasks: List[Task] = []

    for t in tasks:
        # Downstream score (0..100)
        ds_score = (downstream_counts[t.id] / max_downstream * 100.0) if max_downstream > 0 else 0.0
        
        # Urgency score (0..100)
        urg_score = (urgency_scores[t.id] / max_urgency * 100.0) if max_urgency > 0 else 0.0
        
        # Critical path score (0 or 100)
        is_crit = t.id in critical_nodes
        cp_score = 100.0 if is_crit else 0.0

        # Formula: 50% downstream + 30% urgency + 20% critical path
        final_score = int(round(0.50 * ds_score + 0.30 * urg_score + 0.20 * cp_score))
        final_score = max(0, min(100, final_score))

        # Generate reason string
        reasons = []
        if downstream_counts[t.id] > 0:
            reasons.append(f"unlocks {downstream_counts[t.id]} dependent task{'s' if downstream_counts[t.id] > 1 else ''}")
        else:
            reasons.append("final execution task")

        if is_crit:
            reasons.append("belongs to the critical path")

        if t.deadline:
            reasons.append(f"has fixed deadline {t.deadline}")

        reason_text = f"This task {', '.join(reasons)}."
        reason_text = reason_text[0].upper() + reason_text[1:]

        # Create updated task copy
        updated_task = t.model_copy(update={
            "execution_level": execution_levels[t.id],
            "priority_score": final_score,
            "priority_reason": reason_text,
            "is_critical": is_crit
        })
        updated_tasks.append(updated_task)

    # Sort by execution_level ascending, then priority_score descending
    updated_tasks.sort(key=lambda item: (item.execution_level or 1, -(item.priority_score or 0)))

    return updated_tasks
