import { test, expect } from "@playwright/test";

test("AI builder uses the backend preview and explicit confirmation contracts", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("constraintcanvas.session", JSON.stringify({ token: "test-token", expiresAt: Date.now() + 60000 })));
  await page.route("**/api/auth/me", route => route.fulfill({ json: { id: 1, name: "Test User", email: "test@example.com" } }));
  await page.route("**/api/plans/42/context", route => route.fulfill({ json: { plan_id: 42, memory_enabled: false, relevant_context: [], requires_confirmation: true } }));
  const draft = {
    plan: { name: "Release", description: null, planning_start: null, planning_end: "2026-09-18T18:00:00Z" },
    tasks: [{ client_id: "dev", name: "Development", duration_value: "3", duration_unit: "hours", priority: "medium", earliest_start: null, deadline: null, deadline_text: null },
      { client_id: "test", name: "Testing", duration_value: "90", duration_unit: "minutes", priority: "critical", earliest_start: null, deadline: "2026-09-18T17:00:00Z", deadline_text: "5 PM" }],
    resources: [{ client_id: "ravi", name: "Ravi", resource_type: "developer", capacity: 1, availability: [] }],
    dependencies: [{ before_task_id: "dev", after_task_id: "test" }],
    requirements: [{ task_id: "test", resource_type: "developer", quantity: 1, required_resource_id: "ravi" }],
    constraints: [], custom_fields: [], custom_values: {}, evidence: [], ambiguities: [],
    missing_information: [{ field: "plan.planning_start", reason: "Missing start" }],
  };
  let confirmed = false;
  await page.route("**/api/ai/parse-plan", async route => {
    expect(route.request().postDataJSON()).toEqual({ text: "Development takes 3 hours. Testing takes 90 minutes after Development." });
    await route.fulfill({ json: { status: "needs_clarification", draft, questions: [{ id: "q1", field: "plan.planning_start", reason: "Missing start", question: "Please confirm planning start", allowed_answers: [] }], errors: [], requires_confirmation: true } });
  });
  await page.route("**/api/ai/confirm-plan", async route => {
    const body = route.request().postDataJSON();
    expect(Object.keys(body).sort()).toEqual(["answers", "confirmed", "draft"]);
    expect(body.confirmed).toBe(true);
    expect(body.draft.tasks[1].priority).toBe("critical");
    expect(body.draft.plan.planning_start).toBe("2026-09-18T09:00:00Z");
    expect(body.answers).toContainEqual({field: "plan.planning_start", value: "2026-09-18T09:00:00Z"});
    confirmed = true;
    await route.fulfill({ status: 201, json: { status: "created", plan_id: 42, created_counts: {tasks: 2, resources: 1} } });
  });
  await page.goto("/plans/ai-create");
  await page.getByLabel("Describe your planning problem in plain English").fill("Development takes 3 hours. Testing takes 90 minutes after Development.");
  await page.getByRole("button", {name: "Analyze Requirements"}).click();
  await expect(page.getByRole("heading", {name: "Needs Confirmation"})).toBeVisible();
  await expect(page.getByLabel("Task 1 name")).toHaveValue("Development");
  await expect(page.getByLabel("Task 1 duration", {exact: true})).toHaveValue("3");
  await expect(page.getByText("Specific resource: Ravi")).toBeVisible();
  expect(confirmed).toBe(false);
  await page.getByLabel("Plan planning start").fill("2026-09-18T09:00:00Z");
  await page.getByRole("button", {name: "Confirm & Create Plan"}).click();
  await expect(page.getByRole("heading", {name: "Plan created successfully"})).toBeVisible();
  expect(confirmed).toBe(true);
});
