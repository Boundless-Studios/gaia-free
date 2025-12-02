/**
 * Playwright test for Audio Debug Page
 *
 * Tests the /debug/audio page functionality:
 * - Queueing multiple audio items using existing mp3s
 * - WebSocket message monitoring
 * - Audio playback status display
 *
 * Run with: npx playwright test audio-debug.spec.js --headed
 */

import { test, expect } from '@playwright/test';

test.describe('Audio Debug Page', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to debug page
    await page.goto('http://localhost:5173/debug/audio');
  });

  test('should load debug page with correct title', async ({ page }) => {
    // Check page title
    await expect(page.locator('h1')).toHaveText('🎵 Audio Playback Debug');

    // Check subtitle
    await expect(page.locator('.debug-subtitle')).toHaveText('Test audio queue and playback system');
  });

  test('should have default form values', async ({ page }) => {
    // Check default session ID
    const sessionInput = page.getByTestId('session-id-input');
    await expect(sessionInput).toHaveValue('debug-session');

    // Check default number of items
    const numItemsInput = page.getByTestId('num-items-input');
    await expect(numItemsInput).toHaveValue('3');

    // Check button text
    const queueButton = page.getByTestId('queue-audio-button');
    await expect(queueButton).toHaveText('Queue 3 Audio Items');
  });

  test('should update button text when number of items changes', async ({ page }) => {
    const numItemsInput = page.getByTestId('num-items-input');
    const queueButton = page.getByTestId('queue-audio-button');

    // Change to 1 item
    await numItemsInput.fill('1');
    await expect(queueButton).toHaveText('Queue 1 Audio Item');

    // Change to 5 items
    await numItemsInput.fill('5');
    await expect(queueButton).toHaveText('Queue 5 Audio Items');
  });

  test('should display playback status section', async ({ page }) => {
    // Check status section exists
    await expect(page.locator('.playback-status h2')).toHaveText('Playback Status');

    // Check status items
    await expect(page.getByTestId('current-session')).toBeVisible();
    await expect(page.getByTestId('is-streaming')).toBeVisible();
    await expect(page.getByTestId('is-muted')).toBeVisible();
    await expect(page.getByTestId('pending-chunks')).toBeVisible();
  });

  test('should display WebSocket messages section', async ({ page }) => {
    // Check WebSocket section exists
    await expect(page.locator('.ws-messages h2')).toHaveText('WebSocket Messages');

    // Check clear button exists
    const clearButton = page.getByTestId('clear-messages-button');
    await expect(clearButton).toBeVisible();

    // Check messages container exists
    await expect(page.getByTestId('ws-messages-container')).toBeVisible();
  });

  test('should queue audio items (requires backend running)', async ({ page }) => {
    // This test requires the backend to be running
    // Skip if backend is not available
    const response = await page.request.get('http://localhost:8000/api/health').catch(() => null);

    if (!response || !response.ok()) {
      test.skip(true, 'Backend not running, skipping integration test');
      return;
    }

    // Set custom session ID
    const sessionInput = page.getByTestId('session-id-input');
    await sessionInput.fill('playwright-test-session');

    // Set number of items to 2
    const numItemsInput = page.getByTestId('num-items-input');
    await numItemsInput.fill('2');

    // Click queue button
    const queueButton = page.getByTestId('queue-audio-button');
    await queueButton.click();

    // Wait for success message
    const successMessage = page.getByTestId('success-message');
    await expect(successMessage).toBeVisible({ timeout: 10000 });

    // Check success message content
    await expect(successMessage).toContainText('Queued 2 audio items for testing');

    // Check that WebSocket messages appear
    const wsContainer = page.getByTestId('ws-messages-container');
    await expect(wsContainer.locator('.message-item')).not.toHaveCount(0, { timeout: 5000 });
  });

  test('should clear WebSocket messages', async ({ page }) => {
    const clearButton = page.getByTestId('clear-messages-button');
    const wsContainer = page.getByTestId('ws-messages-container');

    // Initially should show "no messages"
    await expect(wsContainer.locator('.no-messages')).toBeVisible();

    // Click clear button (even with no messages)
    await clearButton.click();

    // Should still show no messages
    await expect(wsContainer.locator('.no-messages')).toBeVisible();
  });

  test('should handle session ID changes', async ({ page }) => {
    const sessionInput = page.getByTestId('session-id-input');

    // Change session ID
    await sessionInput.fill('custom-session-123');
    await expect(sessionInput).toHaveValue('custom-session-123');
  });

  test('should enforce number of items limits', async ({ page }) => {
    const numItemsInput = page.getByTestId('num-items-input');

    // Check min value (1)
    await numItemsInput.fill('0');
    // Input should respect min="1"
    await expect(numItemsInput).toHaveAttribute('min', '1');

    // Check max value (10)
    await expect(numItemsInput).toHaveAttribute('max', '10');
  });
});
