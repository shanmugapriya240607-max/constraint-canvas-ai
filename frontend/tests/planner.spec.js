import { test, expect } from '@playwright/test';

test.describe('Create Plan Wizard', () => {
  test.beforeEach(async ({ page }) => {
    // Mock user session
    await page.addInitScript(() => {
      sessionStorage.setItem('constraintcanvas.session', JSON.stringify({
        token: 'test-token',
        expiresAt: Date.now() + 3600000
      }));
    });
    // Mock the me endpoint to keep the session alive
    await page.route('**/api/auth/me', async route => {
      await route.fulfill({
        json: { id: 1, email: 'test@example.com', name: 'Test User' }
      });
    });
    
    await page.goto('/plans/new');
  });

  test('validates plan details step', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Plan Details' })).toBeVisible();
    
    // Check Next button is disabled initially
    const nextBtn = page.getByRole('button', { name: 'Next' });
    await expect(nextBtn).toBeDisabled();

    // Fill details
    await page.fill('input[name="name"]', 'My New Plan');
    await page.fill('input[name="planningStart"]', '2027-01-01T10:00');
    await page.fill('input[name="planningEnd"]', '2026-01-01T10:00'); // invalid (end before start)
    
    await expect(page.locator('.error-message')).toContainText('End time must be later than start time');
    await expect(nextBtn).toBeDisabled();

    // Fix end time
    await page.fill('input[name="planningEnd"]', '2027-01-02T10:00');
    await expect(page.locator('.error-message')).not.toBeVisible();
    await expect(nextBtn).toBeEnabled();
    await nextBtn.click();
    
    // Proceeded to Resources
    await expect(page.getByRole('heading', { name: 'Resources' })).toBeVisible();
  });

  test('allows adding and removing resources', async ({ page }) => {
    // Fill step 1 to proceed
    await page.fill('input[name="name"]', 'Plan 1');
    await page.fill('input[name="planningStart"]', '2027-01-01T10:00');
    await page.fill('input[name="planningEnd"]', '2027-01-02T10:00');
    await page.getByRole('button', { name: 'Next' }).click();

    // Add resource
    await page.getByRole('button', { name: 'Add Resource' }).click();
    const editForm = page.locator('.edit-form');
    await expect(editForm).toBeVisible();
    
    // By default it has empty name, disabled done
    const doneBtn = editForm.getByRole('button', { name: 'Done' });
    await expect(doneBtn).toBeDisabled();

    await editForm.getByRole('textbox').first().fill('Developer 1');
    await expect(doneBtn).toBeEnabled();
    await doneBtn.click();
    
    await expect(page.locator('.item-details').filter({ hasText: 'Developer 1' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Next' })).toBeEnabled();

    // Remove resource
    await page.locator('.icon-button.danger').click();
    await expect(page.locator('.empty-state')).toBeVisible();
  });

  test('full success sequence', async ({ page }) => {
    // Mock the endpoints
    await page.route('**/api/plans', async route => {
      await route.fulfill({ json: { id: 'p1' } });
    });
    await page.route('**/api/plans/p1/resources', async route => {
      await route.fulfill({ json: { id: 'r1' } });
    });
    await page.route('**/api/plans/p1/resources/r1/availability', async route => {
      await route.fulfill({ json: { id: 'a1' } });
    });
    await page.route('**/api/plans/p1/tasks', async route => {
      await route.fulfill({ json: { id: 't1' } });
    });
    await page.route('**/api/plans/p1/tasks/t1/requirements', async route => {
      expect(route.request().postDataJSON()).toHaveProperty('required_resource_id');
      expect(route.request().postDataJSON()).not.toHaveProperty('specific_resource_id');
      await route.fulfill({ json: { id: 'req1' } });
    });
    await page.route('**/api/plans/p1/dependencies', async route => {
      await route.fulfill({ json: { id: 'dep1' } });
    });
    await page.route('**/api/plans/p1/constraints', async route => {
      expect(route.request().postDataJSON().parameters.deadline).toMatch(/Z$/);
      expect(route.request().postDataJSON()).not.toHaveProperty('definition');
      await route.fulfill({ json: { id: 'c1' } });
    });

    // 1. Details
    await page.fill('input[name="name"]', 'Integration Test Plan');
    await page.fill('input[name="planningStart"]', '2027-01-01T10:00');
    await page.fill('input[name="planningEnd"]', '2027-01-02T10:00');
    await page.getByRole('button', { name: 'Next' }).click();

    // 2. Resources
    await page.getByRole('button', { name: 'Add Resource' }).click();
    await page.locator('.edit-form input').first().fill('Test Dev');
    await page.locator('.edit-form button:text("Done")').click();
    await page.getByRole('button', { name: 'Next' }).click();

    // 3. Availability
    await page.getByRole('button', { name: 'Add Availability Window' }).click();
    await page.locator('input[type="datetime-local"]').first().fill('2027-01-01T11:00');
    await page.locator('input[type="datetime-local"]').nth(1).fill('2027-01-01T15:00');
    await page.getByRole('button', { name: 'Next' }).click();

    // 4. Tasks
    await page.getByRole('button', { name: 'Add Task' }).click();
    await page.locator('.edit-form input').first().fill('Test Task 1');
    await page.locator('.edit-form button:text("Done")').click();
    
    // Add second task for dependency
    await page.getByRole('button', { name: 'Add Task' }).click();
    await page.locator('.edit-form input').first().fill('Test Task 2');
    await page.locator('.edit-form button:text("Done")').click();
    await page.getByRole('button', { name: 'Next' }).click();

    // 5. Requirements
    await page.getByRole('button', { name: 'Add Requirement' }).first().click();
    // Default selects first unique type, we can just proceed
    await page.getByRole('button', { name: 'Next' }).click();

    // 6. Dependencies
    await page.getByRole('button', { name: 'Add Dependency' }).click();
    // Select self to see error
    await page.locator('select').first().selectOption({ label: 'Test Task 1' });
    await page.locator('select').nth(1).selectOption({ label: 'Test Task 1' });
    await expect(page.locator('.error-message')).toContainText('cannot depend on itself');
    // Fix dependency
    await page.locator('select').nth(1).selectOption({ label: 'Test Task 2' });
    await expect(page.locator('.error-message')).not.toBeVisible();
    await page.getByRole('button', { name: 'Next' }).click();

    // 7. Constraints
    await page.getByRole('button', { name: 'Add Constraint' }).click();
    await page.locator('select').nth(2).selectOption({ label: 'Test Task 1' }); // deadline constraint
    await page.locator('.edit-form input[type="datetime-local"]').fill('2027-01-01T15:00');
    await page.locator('.edit-form button:text("Done")').click();
    await page.getByRole('button', { name: 'Next' }).click();

    // 8. Review
    await expect(page.getByRole('heading', { name: 'Review Your Plan' })).toBeVisible();
    await expect(page.locator('text=Integration Test Plan')).toBeVisible();
    
    // Submit
    await page.getByRole('button', { name: 'Create Plan' }).click();
    
    // Success Screen
    await expect(page.getByRole('heading', { name: 'Plan Created Successfully!' })).toBeVisible();
    await expect(page.locator('.stat-value').first()).toContainText('2'); // 2 tasks
  });

  test('preserves state on api failure', async ({ page }) => {
    page.on('console', msg => console.log('BROWSER:', msg.text()));

    // Mock the endpoint to fail
    await page.route('**/api/plans', async route => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ status: 500, json: { detail: 'Database error' } });
      } else if (route.request().method() === 'OPTIONS') {
        await route.fulfill({ status: 200, headers: { 'Access-Control-Allow-Origin': '*' } });
      } else {
        await route.continue();
      }
    });

    // 1. Details
    await page.fill('input[name="name"]', 'Fail Plan');
    await page.fill('input[name="planningStart"]', '2027-01-01T10:00');
    await page.fill('input[name="planningEnd"]', '2027-01-02T10:00');
    await page.getByRole('button', { name: 'Next' }).click();

    // Skip to end (Next -> Next -> etc.)
    for(let i=0; i<6; i++) {
      await page.getByRole('button', { name: 'Next' }).click();
    }

    // Now on Review screen
    await page.getByRole('button', { name: 'Create Plan' }).click();
    
    // Should show error and stay on Review
    const errorText = await page.locator('.notice.error').textContent({ timeout: 2000 }).catch(() => null);
    if (!errorText) {
      console.log("No error found!");
    }
    await expect(page.locator('.notice.error')).toContainText('temporarily unavailable');
    await expect(page.getByRole('heading', { name: 'Review Your Plan' })).toBeVisible();
  });
});
