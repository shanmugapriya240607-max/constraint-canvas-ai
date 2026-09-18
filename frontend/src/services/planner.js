import { api } from "./api";

export async function createPlan(data) {
  return api("/api/plans", { method: "POST", body: data });
}

export async function createResource(planId, data) {
  return api(`/api/plans/${planId}/resources`, { method: "POST", body: data });
}

export async function createAvailability(planId, resourceId, data) {
  return api(`/api/plans/${planId}/resources/${resourceId}/availability`, {
    method: "POST",
    body: data,
  });
}

export async function createTask(planId, data) {
  return api(`/api/plans/${planId}/tasks`, { method: "POST", body: data });
}

export async function createTaskRequirement(planId, taskId, data) {
  return api(`/api/plans/${planId}/tasks/${taskId}/requirements`, {
    method: "POST",
    body: data,
  });
}

export async function createDependency(planId, data) {
  return api(`/api/plans/${planId}/dependencies`, { method: "POST", body: data });
}

export async function createConstraint(planId, data) {
  return api(`/api/plans/${planId}/constraints`, { method: "POST", body: data });
}

export async function submitFullPlan(wizardState) {
  // Returns counts for the success screen
  const counts = {
    tasks: 0,
    resources: 0,
    dependencies: 0,
    constraints: 0,
  };

  // 1. Create Plan
  const planPayload = {
    name: wizardState.planDetails.name,
    description: wizardState.planDetails.description || null,
    planning_start: new Date(wizardState.planDetails.planningStart).toISOString(),
    planning_end: new Date(wizardState.planDetails.planningEnd).toISOString(),
  };
  
  const planRes = await createPlan(planPayload);
  const planId = planRes.id || planRes.plan_id; // accommodate either

  // 2. Create Resources and map frontend IDs to backend IDs
  const resourceIdMap = {}; // { tempId: backendId }
  for (const res of wizardState.resources) {
    const resourcePayload = {
      name: res.name,
      resource_type: res.type,
      capacity: parseInt(res.capacity, 10),
      cost_per_hour: res.cost ? parseFloat(res.cost) : null,
      active: res.active !== false, // default true
    };
    const createdRes = await createResource(planId, resourcePayload);
    const backendResId = createdRes.id || createdRes.resource_id;
    resourceIdMap[res.id] = backendResId;
    counts.resources++;

    // 3. Create Availability for this resource
    const availabilities = wizardState.availabilities.filter(
      (a) => a.resourceId === res.id
    );
    for (const avail of availabilities) {
      await createAvailability(planId, backendResId, {
        available_from: new Date(avail.availableFrom).toISOString(),
        available_until: new Date(avail.availableUntil).toISOString(),
      });
    }
  }

  // 4. Create Tasks and map IDs
  const taskIdMap = {};
  for (const task of wizardState.tasks) {
    const taskPayload = {
      name: task.name,
      description: task.description || null,
      duration_value: parseFloat(task.durationValue),
      duration_unit: task.durationUnit,
      priority: task.priority,
      earliest_start: task.earliestStart
        ? new Date(task.earliestStart).toISOString()
        : null,
      deadline: task.deadline ? new Date(task.deadline).toISOString() : null,
    };
    const createdTask = await createTask(planId, taskPayload);
    const backendTaskId = createdTask.id || createdTask.task_id;
    taskIdMap[task.id] = backendTaskId;
    counts.tasks++;

    // 5. Create Requirements for this task
    const reqs = wizardState.requirements.filter((r) => r.taskId === task.id);
    for (const req of reqs) {
      await createTaskRequirement(planId, backendTaskId, {
        resource_type: req.resourceType,
        quantity: parseInt(req.quantity, 10),
        required_resource_id: req.specificResourceId
          ? resourceIdMap[req.specificResourceId] || null
          : null,
      });
    }
  }

  // 6. Create Dependencies
  for (const dep of wizardState.dependencies) {
    await createDependency(planId, {
      before_task_id: taskIdMap[dep.beforeTaskId],
      after_task_id: taskIdMap[dep.afterTaskId],
    });
    counts.dependencies++;
  }

  // 7. Create Constraints
  for (const constraint of wizardState.constraints) {
    // We map any nested IDs inside constraint definitions
    const mappedDefinition = { ...constraint.definition };
    if (mappedDefinition.task_id) {
      mappedDefinition.task_id = taskIdMap[mappedDefinition.task_id];
    }
    if (mappedDefinition.resource_id) {
      mappedDefinition.resource_id = resourceIdMap[mappedDefinition.resource_id];
    }
    if (mappedDefinition.before_task_id) {
      mappedDefinition.before_task_id = taskIdMap[mappedDefinition.before_task_id];
    }
    if (mappedDefinition.after_task_id) {
      mappedDefinition.after_task_id = taskIdMap[mappedDefinition.after_task_id];
    }
    
    for (const field of ["deadline", "available_from", "available_until", "preferred_before"]) {
      if (mappedDefinition[field]) mappedDefinition[field] = new Date(mappedDefinition[field]).toISOString();
    }
    await createConstraint(planId, {
      constraint_type: constraint.type,
      hardness: constraint.hardness,
      weight: constraint.hardness === "soft" ? parseFloat(constraint.weight || 1.0) : null,
      parameters: mappedDefinition,
    });
    counts.constraints++;
  }

  return { planId, counts };
}

export async function solvePlan(planId) {
  return api(`/api/plans/${planId}/solve`, { method: "POST", timeoutMs: 40000 });
}

export async function getPlanAnalysis(planId) {
  return api(`/api/plans/${planId}/analysis`, { method: "GET" });
}

export async function getSolverRuns(planId) {
  return api(`/api/plans/${planId}/runs`, { method: "GET" });
}

export async function getSolverRun(planId, runId) {
  return api(`/api/plans/${planId}/runs/${runId}`, { method: "GET" });
}

export async function getFullPlan(planId) {
  return api(`/api/plans/${planId}/full`, { method: "GET" });
}

export async function getPlans() {
  return api(`/api/plans`, { method: "GET" });
}

export async function getResources(planId) {
  return api(`/api/plans/${planId}/resources`, { method: "GET" });
}

export async function getTasks(planId) {
  return api(`/api/plans/${planId}/tasks`, { method: "GET" });
}
