import { test, expect } from '@playwright/test';

test.describe('What-If Simulator', () => {
  test.beforeEach(async ({ page }) => {
    // Mock user session
    await page.addInitScript(() => {
      sessionStorage.setItem('constraintcanvas.session', JSON.stringify({
        token: 'test-token',
        expiresAt: Date.now() + 3600000
      }));
    });

    // Mock user auth
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        json: { id: 1, email: 'test@example.com', name: 'Test User' },
      });
    });

    // Mock plans list
    await page.route('**/api/plans', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          json: [{ id: 1, name: 'Plan 1' }]
        });
      } else {
        route.continue();
      }
    });

    // Mock specific plan baseline
    await page.route('**/api/plans/1/analysis', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          plan_id: 1,
          status: 'optimal',
          health: { score: 88, grade: 'good', factors: [] },
          risks: [],
          bottlenecks: [],
          issues: [],
          recovery_options: []
        }
      });
    });

    await page.route('**/api/plans/1/runs', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 1, plan_id: 1, solver_status: 'optimal', makespan_minutes: 60 }]
      });
    });
    
    await page.route('**/api/plans/1/runs/1', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 1, result: { schedule: [{ task_name: 'T1', duration_minutes: 60 }] }
        }
      });
    });

    await page.route('**/api/plans/1/resources', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 101, name: 'Ravi', resource_type: 'developer', capacity: 1 }]
      });
    });

    await page.route('**/api/plans/1/tasks', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{ id: 201, name: 'Develop Feature', duration_minutes: 60 }]
      });
    });
  });

  test('loads plan selection when no planId is provided', async ({ page }) => {
    await page.goto('/what-if');
    await expect(page.locator('h1')).toHaveText('Select a Plan for What-If Analysis');
    await expect(page.locator('.plan-list')).toContainText('Plan 1');
  });

  test('loads baseline and shows simulator UI', async ({ page }) => {
    await page.goto('/plans/1/what-if');
    await expect(page.locator('h1')).toHaveText('What-If Simulator');
    await expect(page.locator('.tag.warning')).toHaveText('Simulation only — the original plan remains unchanged.');
    
    // Baseline state is visible
    await expect(page.locator('.empty-state')).toContainText('Baseline Plan');
    await expect(page.locator('.baseline-metrics')).toContainText('optimal');
    await expect(page.locator('.baseline-metrics')).toContainText('Issues: 0');
  });

  test('can run a simulation with multiple changes and see impact', async ({ page }) => {
    // Mock simulation response
    await page.route('**/api/plans/1/what-if', async (route) => {
      expect(route.request().headers().authorization).toBe('Bearer test-token');
      expect(route.request().postDataJSON().changes[0].resource_id).toBe(101);
      await route.fulfill({
        status: 200,
        json: {
          baseline: { status: 'optimal', makespan_minutes: 60, health_score: 88, deadline_violations: 0 },
          scenario: { status: 'feasible', makespan_minutes: 150, health_score: 63, deadline_violations: 1 },
          schedule: [], impact: { makespan_change_minutes: 90, health_change: -25, new_issues: [{ type: "resource_capacity", severity: "critical", message: "Capacity shortage" }], resolved_issues: [] }
        }
      });
    });

    await page.goto('/plans/1/what-if');
    
    // Add resource unavailable
    await page.click('button:has-text("+ Add Change")');
    await page.selectOption('.change-item:nth-child(1) select', 'resource_unavailable');
    await page.selectOption('.change-item:nth-child(1) select:nth-of-type(2)', '101'); // Ravi

    await page.click('button:has-text("Run What-If")');

    // Wait for simulation result
    await expect(page.locator('.impact-summary')).toBeVisible();
    await expect(page.locator('.impact-details')).toContainText('Makespan: +90 minutes');
    await expect(page.locator('.impact-details')).toContainText('Health: -25');
    await expect(page.locator('.impact-details')).toContainText('New Issues: 1');
  });

  test('can save scenarios and compare them', async ({ page }) => {
    await page.route('**/api/plans/1/compare-scenarios', async (route) => {
      expect(route.request().headers().authorization).toBe('Bearer test-token');
      await route.fulfill({
        status: 200,
        json: {
          baseline: { status: 'optimal', makespan_minutes: 60, health_score: 88, deadline_violations: 0 },
          scenarios: [
            { name: 'S1', status: 'infeasible', makespan_minutes: null, health_score: 0, deadline_violations: 1, issues_count: 1 },
            { name: 'S2', status: 'feasible', makespan_minutes: 50, health_score: 90, deadline_violations: 0, issues_count: 0 }
          ]
        }
      });
    });

    await page.goto('/plans/1/what-if');
    
    // Add change for S1
    await page.click('button:has-text("+ Add Change")');
    await page.selectOption('.change-item:nth-child(1) select', 'resource_unavailable');
    await page.selectOption('.change-item:nth-child(1) select:nth-of-type(2)', '101');
    
    await page.fill('#scenario-name', 'S1');
    await page.click('button:has-text("Save for Comparison")');
    
    // Remove change, add another for S2
    await page.click('.change-header button'); // remove
    await page.click('button:has-text("+ Add Change")');
    await page.selectOption('.change-item:nth-child(1) select', 'resource_capacity_change');
    await page.selectOption('.change-item:nth-child(1) select:nth-of-type(2)', '101');
    await page.fill('.change-item:nth-child(1) input[type="number"]', '2');
    
    await page.fill('#scenario-name', 'S2');
    await page.click('button:has-text("Save for Comparison")');
    
    // Go to comparison tab
    await page.click('button:has-text("Compare Scenarios")');
    
    // Check saved list
    await expect(page.locator('.scenarios-list')).toContainText('S1');
    await expect(page.locator('.scenarios-list')).toContainText('S2');
    
    await page.click('button.primary:has-text("Compare Scenarios")');
    
    // Wait for comparison result
    await expect(page.locator('.comparison-table')).toBeVisible();
    await expect(page.locator('.comparison-table th').filter({ hasText: 'S1' })).toBeVisible();
    await expect(page.locator('.comparison-table th').filter({ hasText: 'S2' })).toBeVisible();
    
    await expect(page.locator('td', { hasText: /^INFEASIBLE$/ })).toBeVisible();
    await expect(page.locator('td', { hasText: /^FEASIBLE$/ })).toBeVisible();
  });
});
