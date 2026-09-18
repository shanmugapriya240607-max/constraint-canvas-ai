import { api } from "./api";

export async function parseNaturalLanguagePlan(payload) {
  return api("/api/ai/parse-plan", {
    method: "POST",
    body: payload,
    timeoutMs: 130000,
  });
}

export async function confirmParsedPlan(payload) {
  return api("/api/ai/confirm-plan", {
    method: "POST",
    body: payload,
    timeoutMs: 130000,
  });
}
