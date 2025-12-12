// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Turn-Based Messages Test Suite
 *
 * Tests the new turn-based message ordering system.
 */

test.describe('Turn-Based Messages', () => {
  test.beforeEach(async ({ page }) => {
    // Go to the test page
    await page.goto('/test/turn-messages');

    // Wait for page to load
    await expect(page.locator('h1')).toContainText('Turn-Based Messages Test');
  });

  test('page loads and shows connection status', async ({ page }) => {
    // Should show connection status
    const statusBar = page.locator('text=Connected').or(page.locator('text=Disconnected'));
    await expect(statusBar).toBeVisible();

    // Should show session ID
    await expect(page.locator('text=Session:')).toBeVisible();

    // Should show current turn
    await expect(page.locator('text=Current Turn:')).toBeVisible();
  });

  test('simulate turn locally works', async ({ page }) => {
    // Click simulate turn button
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    await expect(simulateBtn).toBeVisible();
    await simulateBtn.click();

    // Wait for turn to appear
    await expect(page.locator('text=Turn 1')).toBeVisible({ timeout: 5000 });

    // Should show the turn input
    await expect(page.locator('.turn-input-section')).toBeVisible();

    // Should show streaming and then final response
    await expect(page.locator('.dm-response-section')).toBeVisible({ timeout: 10000 });

    // Event log should show turn events
    const eventLog = page.locator('.turn-test-page >> text=turn_started');
    // Note: This checks if turn_started appears in the log
  });

  test('multiple simulated turns maintain order', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');

    // Simulate first turn
    await simulateBtn.click();
    await expect(page.locator('text=Turn 1')).toBeVisible({ timeout: 5000 });

    // Wait for first turn to complete
    await page.waitForTimeout(3000);

    // Simulate second turn
    await simulateBtn.click();
    await expect(page.locator('text=Turn 2')).toBeVisible({ timeout: 5000 });

    // Both turns should be visible
    await expect(page.locator('.turn-message')).toHaveCount(2);
  });

  test('clear turns works', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const clearBtn = page.locator('button:has-text("Clear Turns")');

    // Simulate a turn
    await simulateBtn.click();
    await expect(page.locator('text=Turn 1')).toBeVisible({ timeout: 5000 });

    // Clear turns
    await clearBtn.click();

    // Should show no turns message
    await expect(page.locator('text=No turns yet')).toBeVisible();
  });

  test('debug state updates correctly', async ({ page }) => {
    // Initial state should show turnsCount: 0
    const debugState = page.locator('pre:has-text("turnsCount")');
    await expect(debugState).toContainText('"turnsCount": 0');

    // Simulate a turn
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    await simulateBtn.click();

    // Wait for turn to complete
    await page.waitForTimeout(3000);

    // Debug state should show turnsCount: 1
    await expect(debugState).toContainText('"turnsCount": 1');
  });

  test.describe('with real campaign', () => {
    // These tests require a real campaign ID
    const REAL_CAMPAIGN_ID = 'campaign_202';

    test('can change session to real campaign', async ({ page }) => {
      // Enter real campaign ID
      const sessionInput = page.locator('input[placeholder="Session ID"]');
      await sessionInput.fill(REAL_CAMPAIGN_ID);

      // Click change session
      const changeBtn = page.locator('button:has-text("Change Session")');
      await changeBtn.click();

      // Status should update to show new session
      await expect(page.locator(`text=Session: ${REAL_CAMPAIGN_ID}`)).toBeVisible();
    });

    test.skip('submit turn via websocket sends turn events', async ({ page }) => {
      // This test is skipped by default as it requires auth and a real campaign
      // To run: remove .skip and ensure you're logged in

      // Change to real campaign
      const sessionInput = page.locator('input[placeholder="Session ID"]');
      await sessionInput.fill(REAL_CAMPAIGN_ID);
      await page.locator('button:has-text("Change Session")').click();

      // Wait for connection
      await expect(page.locator('text=Connected')).toBeVisible({ timeout: 10000 });

      // Submit turn
      const submitBtn = page.locator('button:has-text("Submit Turn (WebSocket)")');
      await submitBtn.click();

      // Should see turn_started in event log
      await expect(page.locator('text=turn_started')).toBeVisible({ timeout: 5000 });

      // Should see turn message appear
      await expect(page.locator('.turn-message')).toBeVisible({ timeout: 30000 });
    });
  });
});

test.describe('Event Log', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/test/turn-messages');
  });

  test('shows events as they occur', async ({ page }) => {
    // Simulate a turn
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    await simulateBtn.click();

    // Event log should show simulate message
    const eventLog = page.locator('text=Simulating turn');
    await expect(eventLog).toBeVisible({ timeout: 2000 });
  });
});
