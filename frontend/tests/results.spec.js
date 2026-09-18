import { test, expect } from '@playwright/test';

test.describe('Optimization Results', () => {
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
  });

  test('renders optimal result properly', async ({ page }) => {
    // Mock solve
    await page.route('**/api/plans/1/solve', async (route) => {
      await route.fulfill({ status: 200, json: { status: 'optimal' } });
    });
    
    // Mock analysis
    await page.route('**/api/plans/1/analysis', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          plan_id: 1,
          status: 'optimal',
          health: { score: 95, grade: 'good', factors: [{ name: 'Slack', impact: 5, reason: 'Good slack' }] },
          risks: [],
          bottlenecks: [],
          issues: [],
          recovery_options: []
        }
      });
    });

    // Mock runs
    await page.route('**/api/plans/1/runs', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{
          id: 1,
          plan_id: 1,
          solver_status: 'optimal',
          makespan_minutes: 60,
          solve_duration_ms: 1500,
          created_at: new Date().toISOString()
        }]
      });
    });

    // Mock specific run detail
    await page.route('**/api/plans/1/runs/1', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          id: 1,
          plan_id: 1,
          result: {
            schedule: [
              {
                task_id: 1,
                task_name: 'Test Task',
                start_time: new Date().toISOString(),
                end_time: new Date(Date.now() + 60000).toISOString(),
                duration_minutes: 60,
                priority: 'High',
                assigned_resources: [{ resource_id: 1, name: 'Dev', resource_type: 'human', units: 1 }]
              }
            ]
          }
        }
      });
    });

    await page.goto('/plans/1/results');

    // Wait for the loading state to finish
    await expect(page.locator('.results-loading')).toBeHidden({ timeout: 5000 });

    // Validate headers
    await expect(page.locator('h1')).toHaveText('Plan Optimization Results');
    await expect(page.locator('.status-badge h2')).toHaveText('OPTIMAL PLAN');

    // Validate Gantt Chart
    await expect(page.locator('.gantt-chart-container')).toBeVisible();
    await expect(page.locator('.gantt-label').first()).toHaveText('Test Task');
    
    // Validate Health
    await expect(page.locator('.health-score-display .score-number')).toHaveText('95');
  });

  test('renders infeasible result with recovery options', async ({ page }) => {
    // Mock solve
    await page.route('**/api/plans/2/solve', async (route) => {
      await route.fulfill({ status: 200, json: { status: 'infeasible' } });
    });
    
    // Mock analysis
    await page.route('**/api/plans/2/analysis', async (route) => {
      await route.fulfill({
        status: 200,
        json: {
          plan_id: 2,
          status: 'infeasible',
          health: { score: 0, grade: 'critical', factors: [] },
          risks: [],
          bottlenecks: [],
          issues: [{ type: 'Capacity Shortfall', severity: 'critical', message: 'Not enough devs' }],
          recovery_options: [{ title: 'Add Resource', explanation: 'Add a dev', changes_required: '1 dev', affected_entities: ['task_1'] }]
        }
      });
    });

    // Mock runs
    await page.route('**/api/plans/2/runs', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{
          id: 2,
          plan_id: 2,
          solver_status: 'infeasible',
          makespan_minutes: null,
          solve_duration_ms: 1200,
          created_at: new Date().toISOString()
        }]
      });
    });

    await page.goto('/plans/2/results');

    await expect(page.locator('.results-loading')).toBeHidden({ timeout: 5000 });

    // Validate headers
    await expect(page.locator('.infeasible-banner h2')).toHaveText('PLAN INFEASIBLE');
    
    // Validate issues
    await expect(page.locator('.issue-message')).toHaveText('Not enough devs');
    
    // Validate recovery options
    await expect(page.locator('.recovery-card h4')).toHaveText('Add Resource');
  });
  
  test('handles api failure gracefully', async ({ page }) => {
    await page.route('**/api/plans/3/solve', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Server Error' } });
    });

    await page.goto('/plans/3/results');

    await expect(page.locator('.results-error')).toBeVisible();
    await expect(page.locator('.notice.error')).toContainText('temporarily unavailable');
  });
});
