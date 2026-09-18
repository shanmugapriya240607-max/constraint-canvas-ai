import { test, expect } from '@playwright/test';
test('debug', async ({ page }) => {
  page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
  page.on('pageerror', err => console.log('BROWSER ERROR:', err.message));
  await page.goto('/login');
  await page.waitForTimeout(2000);
  const content = await page.content();
  console.log('HTML CONTENT LENGTH:', content.length);
  if (true) {
    console.log('HTML CONTENT:', content);
  }
});
