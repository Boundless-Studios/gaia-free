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
    // Should show connection status (with emoji prefixes)
    const statusBar = page.locator('text=/Connected|Disconnected/');
    await expect(statusBar.first()).toBeVisible();

    // Should show session ID
    await expect(page.locator('text=/Session:/i')).toBeVisible();

    // Should show current turn
    await expect(page.locator('text=/Current Turn:/i')).toBeVisible();
  });

  test('simulate turn locally works', async ({ page }) => {
    // Click simulate turn button
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    await expect(simulateBtn).toBeVisible();
    await simulateBtn.click();

    // Wait for turn to appear (badge shows "Turn 1")
    await expect(page.locator('.turn-number-badge:has-text("Turn 1")')).toBeVisible({ timeout: 5000 });

    // Wait for simulation to complete - check debug state shows isProcessing: false
    // This indicates the turn has fully completed (streaming finished)
    const debugState = page.locator('[data-testid="debug-state"]');
    await expect(debugState).toContainText('"isProcessing": false', { timeout: 15000 });

    // Now sections should be fully populated (use .first() since embedded PlayerView also has these)
    await expect(page.locator('.turn-input-section').first()).toBeVisible();
    await expect(page.locator('.dm-response-section').first()).toBeVisible();

    // Should contain the player input (note: shows "Player:" as label)
    await expect(page.locator('.turn-input-section').first()).toContainText('I approach the mysterious door');
  });

  test('multiple simulated turns maintain order', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const debugState = page.locator('[data-testid="debug-state"]');
    // Scope to main test area (before embedded PlayerView section)
    const mainTestArea = page.locator('h3:has-text("Turn Messages")').locator('..');

    // Simulate first turn
    await simulateBtn.click();
    await expect(page.locator('.turn-number-badge:has-text("Turn 1")').first()).toBeVisible({ timeout: 5000 });

    // Wait for first turn to fully complete (isProcessing becomes false)
    await expect(debugState).toContainText('"isProcessing": false', { timeout: 15000 });

    // Now button should be enabled again - simulate second turn
    await simulateBtn.click();
    await expect(page.locator('.turn-number-badge:has-text("Turn 2")').first()).toBeVisible({ timeout: 5000 });

    // Wait for second turn to complete
    await expect(debugState).toContainText('"turnsCount": 2', { timeout: 15000 });

    // Both turns should be visible in the main test area
    await expect(mainTestArea.locator('.turn-message')).toHaveCount(2);
  });

  test('clear turns works', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const clearBtn = page.locator('button:has-text("Clear Turns")');
    const debugState = page.locator('[data-testid="debug-state"]');

    // Simulate a turn
    await simulateBtn.click();
    await expect(page.locator('.turn-number-badge:has-text("Turn 1")')).toBeVisible({ timeout: 5000 });

    // Wait for turn to fully complete (isProcessing becomes false)
    await expect(debugState).toContainText('"isProcessing": false', { timeout: 15000 });

    // Clear turns
    await clearBtn.click();

    // Should show no turns message (partial text match)
    await expect(page.locator('text=/No turns yet/i')).toBeVisible({ timeout: 2000 });

    // Debug state should show turnsCount: 0
    await expect(debugState).toContainText('"turnsCount": 0');
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

test.describe('Tab Switching (PlayerView behavior)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/test/turn-messages');
    await expect(page.locator('h1')).toContainText('Turn-Based Messages Test');
  });

  test('should display tab switch log', async ({ page }) => {
    const tabSwitchLog = page.locator('[data-testid="tab-switch-log"]');
    await expect(tabSwitchLog).toBeVisible();
    await expect(tabSwitchLog).toContainText('No tab switches yet');
  });

  test('should show embedded PlayerView', async ({ page }) => {
    const playerView = page.locator('[data-testid="embedded-player-view"]');
    await expect(playerView).toBeVisible();

    const playerViewInner = page.locator('[data-testid="player-view"]');
    await expect(playerViewInner).toBeVisible();
  });

  test('isProcessing should become true on turn_started', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const stateIndicator = page.locator('[data-testid="player-view-state"]');

    // Initially should be false
    await expect(stateIndicator).toContainText('isProcessing: false');

    // Start the simulation
    await simulateBtn.click();

    // Should quickly become true
    await expect(stateIndicator).toContainText('isProcessing: true', { timeout: 1000 });
  });

  test('tab switch log should show SWITCH_TO_HISTORY on turn start', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const tabSwitchLog = page.locator('[data-testid="tab-switch-log"]');

    // Click simulate
    await simulateBtn.click();

    // Tab switch log should show SWITCH_TO_HISTORY
    await expect(tabSwitchLog).toContainText('SWITCH_TO_HISTORY', { timeout: 2000 });
    await expect(tabSwitchLog).toContainText('isProcessing=true');
  });

  test('tab switch log should show HIGHLIGHT_INTERACT on turn complete', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const tabSwitchLog = page.locator('[data-testid="tab-switch-log"]');

    // Click simulate
    await simulateBtn.click();

    // Wait for turn to complete (streaming takes ~5 seconds in simulation)
    await expect(tabSwitchLog).toContainText('HIGHLIGHT_INTERACT', { timeout: 10000 });
    await expect(tabSwitchLog).toContainText('Processing completed');
  });

  test('embedded PlayerView tab should switch to history during processing', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const playerControls = page.locator('[data-testid="player-controls"]');

    // Initially, voice/Interact tab should be active
    const voiceTab = playerControls.locator('.tab-button').filter({ hasText: /Interact/i });
    const historyTab = playerControls.locator('.tab-button').filter({ hasText: /History/i });

    // Voice tab should be active initially
    await expect(voiceTab).toHaveClass(/active/);

    // Start simulation
    await simulateBtn.click();

    // History tab should become active
    await expect(historyTab).toHaveClass(/active/, { timeout: 2000 });
  });

  test('embedded PlayerView Interact tab should highlight when processing completes', async ({ page }) => {
    const simulateBtn = page.locator('button:has-text("Simulate Turn (Local)")');
    const playerControls = page.locator('[data-testid="player-controls"]');

    // Get the voice/Interact tab
    const voiceTab = playerControls.locator('.tab-button').filter({ hasText: /Interact/i });

    // Start simulation
    await simulateBtn.click();

    // Wait for turn to complete
    await page.waitForTimeout(6000);

    // Voice tab should have highlight-pulse class
    await expect(voiceTab).toHaveClass(/highlight-pulse/, { timeout: 5000 });
  });

  test('debug state shows all streaming state variables', async ({ page }) => {
    const debugState = page.locator('[data-testid="debug-state"]');

    // Should show all the new state variables
    await expect(debugState).toContainText('isAnyTurnStreaming');
    await expect(debugState).toContainText('isCurrentlyProcessing');
    await expect(debugState).toContainText('simulatedTab');
    await expect(debugState).toContainText('highlightInteract');
  });
});
