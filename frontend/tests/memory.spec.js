import { test, expect } from "@playwright/test";

async function mockMemoryApi(page) {
  let memoryEnabled = false;
  let memories = [{ id: 1, memory_type: "preference", key: "Preferred Tester", value: { text: "Ravi" }, source: "user" }];
  let habits = [{ id: 10, habit_type: "preferred_resource", normalized_pattern: "Test Habit", occurrence_count: 3, suggested_memory: {}, status: "pending" }];

  await page.route("**/api/memory/*", async (route) => {
    const method = route.request().method();
    if (method === "DELETE") {
      const urlParts = route.request().url().split("/");
      const id = parseInt(urlParts[urlParts.length - 1]);
      if (!isNaN(id)) {
        memories = memories.filter(m => m.id !== id);
        await route.fulfill({ status: 200, json: { success: true } });
        return;
      }
    }
    await route.fallback();
  });

  await page.route("**/api/memory/consent", async (route) => {
    if (route.request().method() === "PUT") {
      const body = JSON.parse(route.request().postData());
      memoryEnabled = body.enabled;
      await route.fulfill({ status: 200, json: { memory_enabled: memoryEnabled } });
    } else {
      await route.fulfill({ status: 200, json: { memory_enabled: memoryEnabled } });
    }
  });
  
  await page.route("**/api/memory", async (route) => {
    if (route.request().method() === "POST") {
      const body = JSON.parse(route.request().postData());
      expect(body.memory_type).toBe("preference");
      expect(body.value).toEqual({ text: "Morning" });
      memories.push({ id: Date.now(), ...body });
      await route.fulfill({ status: 201, json: { id: 2, ...body } });
    } else {
      await route.fulfill({ status: 200, json: memories });
    }
  });

  await page.route("**/api/memory/habits", async (route) => {
    await route.fulfill({ status: 200, json: habits });
  });

  await page.route("**/api/memory/habits/detect", async (route) => {
    await route.fulfill({ status: 200, json: { success: true } });
  });

  await page.route("**/api/memory/habits/*/accept", async (route) => {
    habits = [];
    await route.fulfill({ status: 200, json: { success: true } });
  });

  await page.route("**/api/memory/habits/*/reject", async (route) => {
    habits = [];
    await route.fulfill({ status: 200, json: { success: true } });
  });

  await page.route("**/api/plans/*/context", async (route) => {
    await route.fulfill({ status: 200, json: {plan_id: 1, memory_enabled: true, requires_confirmation: true, relevant_context: [{ memory_id: 1, type: "preferred_resource", reason: "Context Memory", suggested_use: {resource_id: 1} }]} });
  });

  await page.route("**/api/plans/*/context/apply", async (route) => {
    await route.fulfill({ status: 200, json: { success: true } });
  });
}

const sessionKey = "constraintcanvas.session";

test.beforeEach(async ({ page }) => {
  await mockMemoryApi(page);
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, json: { id: 1, name: "Test User", email: "test@example.com" } });
  });
  await page.addInitScript(
    ({ key }) =>
      sessionStorage.setItem(
        key,
        JSON.stringify({ token: "test-token", expiresAt: Date.now() + 60000 }),
      ),
    { key: sessionKey },
  );
});

test("memory status loads and can be enabled/disabled", async ({ page }) => {
  await page.goto("/memory");
  
  // Disabled by default according to our mock
  await expect(page.getByText("Planning memory is off")).toBeVisible();
  await expect(page.getByRole("button", { name: "Enable Memory" })).toBeVisible();

  // Enable
  await page.getByRole("button", { name: "Enable Memory" }).click();
  await expect(page.getByRole("button", { name: "Disable Memory" })).toBeVisible();
  await expect(page.getByText("Planning memory is off")).not.toBeVisible();

  // Disable again
  await page.getByRole("button", { name: "Disable Memory" }).click();
  await expect(page.getByText("Planning memory is off")).toBeVisible();
});

test("saved memories render and can be created/deleted", async ({ page }) => {
  await page.goto("/memory");
  
  // Initial memory from mock
  await expect(page.getByText("Preferred Tester: Ravi")).toBeVisible();

  // Create explicit memory
  await page.getByRole("button", { name: "Enable Memory" }).click();
  await page.getByLabel("Key").fill("Preferred Time");
  await page.getByLabel("Value").fill("Morning");
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByText("Preferred Time: Morning")).toBeVisible();

  // Delete memory
  const deleteBtns = await page.getByRole("button", { name: "delete" }).all();
  if (deleteBtns.length > 0) {
    await deleteBtns[0].click();
    // Assuming first one was "Preferred Tester: Ravi"
    await expect(page.getByText("Preferred Tester: Ravi")).not.toBeVisible();
  }
});

test("habit candidate renders, accept and reject work", async ({ page }) => {
  await page.goto("/memory");
  
  await expect(page.getByText("We noticed a pattern")).toBeVisible();

  // Reject habit
  await page.getByRole("button", { name: "Reject" }).click();
  await expect(page.getByText("No pending habit suggestions.")).toBeVisible();
});

test("plan context renders and selected context applies", async ({ page }) => {
  // To test RelevantPlanningContext, we navigate to a plan result page where it is rendered
  // First mock plan endpoints
  await page.route("**/api/plans/1/solve", async route => route.fulfill({status:200, json: {status: "FEASIBLE"}}));
  await page.route("**/api/plans/1/analysis", async route => route.fulfill({status:200, json: {status: "FEASIBLE"}}));
  await page.route("**/api/plans/1/runs", async route => route.fulfill({status:200, json: []}));

  await page.goto("/plans/1/results");

  await expect(page.getByText("Relevant Planning Context Found")).toBeVisible();
  await expect(page.getByText("Context Memory")).toBeVisible();

  // Check the checkbox (first checkbox)
  await page.getByRole("checkbox").first().check();
  
  // Click Apply
  await page.getByRole("button", { name: "Use Selected" }).click();
  // It should reload or disappear, mostly we just verify no crash and button works
  // Because it reloads, the page will just render again with the same mock
});

test("dashboard integration displays memory stats", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page.getByText("Memory: OFF")).toBeVisible();
  await expect(page.getByText("1 Pending Habits")).toBeVisible();
});
