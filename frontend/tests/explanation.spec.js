import { test, expect } from '@playwright/test';
const schedule = [1, 2].map(id => ({ task_id: id, task_name: `Task ${id}`, priority: 'high', duration_minutes: 60, start_time: '2026-09-18T09:00:00Z', end_time: '2026-09-18T10:00:00Z', assigned_resources: [] }));
const reasons = ['dependency', 'specific_resource', 'resource_capacity', 'resource_availability', 'deadline', 'priority'].map(kind => ({ kind, message: `Backend ${kind} reason for Task 1.` }));
const explanation = { plan_id: 1, run_id: 7, status: 'optimal', tasks: [{ task_id: 1, reasons }, { task_id: 2, reasons: [{ kind: 'priority', message: 'Backend reason for Task 2 only.' }] }] };
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('constraintcanvas.session', JSON.stringify({ token: 'test-token', expiresAt: Date.now() + 3600000 })));
  const responses = {
    '/api/auth/me': { id: 1, name: 'Tester', email: 'test@example.com' },
    '/api/plans/1/solve': { status: 'optimal' },
    '/api/plans/1/analysis': { status: 'optimal', risks: [], bottlenecks: [], issues: [], recovery_options: [] },
    '/api/plans/1/runs': [{ id: 7, solver_status: 'optimal', makespan_minutes: 60 }],
    '/api/plans/1/runs/7': { id: 7, result: { schedule } },
    '/api/plans/1/context': { relevant_context: [] },
  };
  for (const [path, json] of Object.entries(responses)) await page.route(`**${path}`, route => route.fulfill({ status: 200, json }));
});
async function selectFirst(page) {
  await page.goto('/plans/1/results');
  await page.getByRole('button', { name: 'Show details for Task 1', exact: true }).click();
  return page.locator('.why-schedule-section');
}
test('authenticated explanations show loading then only the selected task reasons', async ({ page }) => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  let calls = 0;
  await page.route('**/api/plans/1/explanation', async route => {
    calls++;
    expect(route.request().method()).toBe('GET');
    expect(route.request().headers().authorization).toBe('Bearer test-token');
    await gate;
    await route.fulfill({ status: 200, json: explanation });
  });
  const panel = await selectFirst(page);
  await expect(panel.getByRole('status')).toHaveText('Loading schedule explanation...');
  release();
  for (const reason of reasons) await expect(panel.locator(`[data-reason-kind="${reason.kind}"]`)).toHaveText(reason.message);
  await expect(panel).not.toContainText('Task 2 only');
  await page.getByRole('button', { name: 'Show details for Task 2', exact: true }).press('Enter');
  await expect(panel).toContainText('Backend reason for Task 2 only.');
  await expect(panel).not.toContainText('reason for Task 1');
  expect(calls).toBe(1);
});
for (const [name, json] of [
  ['empty reasons', { ...explanation, tasks: [{ task_id: 1, reasons: [] }] }],
  ['missing task', { ...explanation, tasks: [] }],
  ['different run', { ...explanation, run_id: 8 }],
  ['infeasible run', { ...explanation, status: 'infeasible', tasks: [] }],
]) test(`handles ${name} without invented reasons`, async ({ page }) => {
  await page.route('**/api/plans/1/explanation', route => route.fulfill({ status: 200, json }));
  const panel = await selectFirst(page);
  await expect(panel).toContainText('No explanation is available for this task in the displayed schedule.');
  await expect(panel.locator('li')).toHaveCount(0);
});
test('explanation error leaves schedule usable', async ({ page }) => {
  await page.route('**/api/plans/1/explanation', route => route.fulfill({ status: 500, json: { detail: 'Internal diagnostic not for clients' } }));
  const panel = await selectFirst(page);
  await expect(panel.getByRole('alert')).toContainText('Could not load the schedule explanation');
  await expect(panel).not.toContainText('Internal diagnostic');
  await expect(page.locator('.gantt-chart-container')).toBeVisible();
  await expect(page.locator('.task-details-panel')).toContainText('Task Details: Task 1');
});
