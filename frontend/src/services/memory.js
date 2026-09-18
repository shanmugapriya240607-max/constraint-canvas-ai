import { api } from "./api";

export async function getMemoryConsent() {
  return api("/api/memory/consent");
}

export async function updateMemoryConsent(enabled) {
  return api("/api/memory/consent", {
    method: "PUT",
    body: { enabled },
  });
}

export async function getMemories() {
  return api("/api/memory");
}

export async function createMemory(payload) {
  return api("/api/memory", {
    method: "POST",
    body: payload,
  });
}

export async function updateMemory(id, payload) {
  return api(`/api/memory/${id}`, {
    method: "PATCH",
    body: payload,
  });
}

export async function deleteMemory(id) {
  return api(`/api/memory/${id}`, {
    method: "DELETE",
  });
}

export async function getHabitCandidates() {
  return api("/api/memory/habits");
}

export async function detectHabits(payload) {
  return api("/api/memory/habits/detect", {
    method: "POST",
    body: payload || {},
  });
}

export async function acceptHabit(id) {
  return api(`/api/memory/habits/${id}/accept`, {
    method: "POST",
  });
}

export async function rejectHabit(id) {
  return api(`/api/memory/habits/${id}/reject`, {
    method: "POST",
  });
}

export async function getPlanContext(planId) {
  return api(`/api/plans/${planId}/context`);
}

export async function applyPlanContext(planId, memoryIds) {
  return api(`/api/plans/${planId}/context/apply`, {
    method: "POST",
    body: { memory_ids: memoryIds },
  });
}
