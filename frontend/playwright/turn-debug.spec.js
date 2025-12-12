// @ts-check
import { test, expect } from '@playwright/test';

test('debug turn simulation', async ({ page }) => {
  // Enable console logging
  page.on('console', msg => {
    if (msg.text().includes('TurnMessage') || msg.text().includes('useTurnBasedMessages')) {
      console.log('BROWSER:', msg.text());
    }
  });

  await page.goto('/test/turn-messages');
  await page.waitForTimeout(1000);

  // Click simulate turn
  console.log('Clicking simulate button...');
  await page.locator('button:has-text("Simulate Turn (Local)")').click();

  // Wait for processing to complete
  console.log('Waiting for processing...');
  await page.waitForTimeout(5000);

  // Take screenshot
  await page.screenshot({ path: 'turn-debug-screenshot.png', fullPage: true });
  console.log('Screenshot saved');

  // Log debug state
  const debugState = await page.locator('pre:has-text("turnsCount")').textContent();
  console.log('Debug State:', debugState);

  // Check if turn content appeared
  const turnMessage = page.locator('.turn-message');
  const count = await turnMessage.count();
  console.log('Turn message elements:', count);

  if (count > 0) {
    const html = await turnMessage.first().innerHTML();
    console.log('Turn message HTML:', html.slice(0, 500));
  }
});
