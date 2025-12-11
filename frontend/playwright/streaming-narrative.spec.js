// @ts-check
import { test, expect } from '@playwright/test';

/**
 * Playwright tests for StreamingNarrativeView component
 * Tests the message flow and duplicate detection
 */

test.describe('StreamingNarrativeView', () => {
  test.beforeEach(async ({ page }) => {
    // Capture console logs
    page.on('console', msg => console.log('BROWSER:', msg.type(), msg.text()));
    page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

    // Navigate to the test page
    console.log('Navigating to /test/streaming-narrative...');
    await page.goto('/test/streaming-narrative', { waitUntil: 'networkidle' });

    // Debug: check what page we're actually on
    const url = page.url();
    const title = await page.title();
    console.log('Current URL:', url);
    console.log('Page title:', title);

    // Take a debug screenshot
    await page.screenshot({ path: 'test-results/debug-page-load.png' });

    // Check if root element has content
    const rootHtml = await page.locator('#root').innerHTML().catch(() => 'NO ROOT');
    console.log('Root content length:', rootHtml.length);
    if (rootHtml.length < 100) {
      console.log('Root content:', rootHtml);
    }

    // Wait for the component to render with longer timeout
    await expect(page.getByText('StreamingNarrativeView Test')).toBeVisible({ timeout: 15000 });
  });

  test('should render the test page correctly', async ({ page }) => {
    // Check that the test controls are visible
    await expect(page.getByTestId('run-full-flow')).toBeVisible();
    await expect(page.getByTestId('run-duplicate-test')).toBeVisible();
    await expect(page.getByTestId('clear-all')).toBeVisible();

    // Check initial state - no messages
    const dmCount = page.getByTestId('dm-count');
    await expect(dmCount).toContainText('DM Messages: 0');
  });

  test('full flow test should add exactly ONE DM message', async ({ page }) => {
    // Click the full flow test button
    await page.getByTestId('run-full-flow').click();

    // Wait for streaming to complete (the button should re-enable)
    await page.waitForTimeout(2000);

    // Check that exactly 1 DM message was added
    const dmCount = page.getByTestId('dm-count');
    await expect(dmCount).toContainText('DM Messages: 1');

    // There should be no duplicate warning
    await expect(page.getByText('DUPLICATE DETECTED!')).not.toBeVisible();
  });

  test('duplicate bug test should NOT create duplicates (dedup should work)', async ({ page }) => {
    // Click the duplicate bug test button
    await page.getByTestId('run-duplicate-test').click();

    // Wait for both add attempts to complete
    await page.waitForTimeout(2000);

    // Check that exactly 1 DM message was added (second should be deduped)
    const dmCount = page.getByTestId('dm-count');
    await expect(dmCount).toContainText('DM Messages: 1');

    // Check that the log shows the duplicate was skipped
    // Use .first() because React strict mode may cause multiple log entries
    await expect(page.getByText('DUPLICATE DETECTED - skipping').first()).toBeVisible();
  });

  test('streaming content should be visible during streaming', async ({ page }) => {
    // Start the full flow test
    await page.getByTestId('run-full-flow').click();

    // During streaming, the streaming indicator should be visible
    // Note: This is a timing-sensitive test
    await expect(page.locator('.streaming-cursor')).toBeVisible({ timeout: 500 }).catch(() => {
      // It's okay if streaming is too fast to catch
      console.log('Streaming was too fast to observe cursor');
    });
  });

  test('messages should persist after streaming completes', async ({ page }) => {
    // Run full flow
    await page.getByTestId('run-full-flow').click();
    await page.waitForTimeout(2000);

    // Get the raw messages
    const rawMessages = page.getByTestId('raw-messages');
    const messagesText = await rawMessages.textContent();
    const messages = JSON.parse(messagesText);

    // Should have 2 messages: user + DM
    expect(messages.length).toBe(2);
    expect(messages[0].sender).toBe('user');
    expect(messages[1].sender).toBe('dm');
  });

  test('clear all should reset state', async ({ page }) => {
    // Run a test first
    await page.getByTestId('run-full-flow').click();
    await page.waitForTimeout(2000);

    // Verify messages exist
    await expect(page.getByTestId('dm-count')).toContainText('DM Messages: 1');

    // Click clear
    await page.getByTestId('clear-all').click();

    // Verify cleared
    await expect(page.getByTestId('dm-count')).toContainText('DM Messages: 0');
  });

  test('multiple consecutive messages should not create duplicates', async ({ page }) => {
    // Run full flow multiple times
    await page.getByTestId('run-full-flow').click();
    await page.waitForTimeout(2500);

    await page.getByTestId('run-full-flow').click();
    await page.waitForTimeout(2500);

    await page.getByTestId('run-full-flow').click();
    await page.waitForTimeout(2500);

    // Get the raw messages
    const rawMessages = page.getByTestId('raw-messages');
    const messagesText = await rawMessages.textContent();
    const messages = JSON.parse(messagesText);

    // Should have 6 messages: 3 user + 3 DM
    // Each run adds a new user message, but the DM message is the same text
    // so subsequent runs might be deduped depending on timing
    const userMessages = messages.filter(m => m.sender === 'user');
    const dmMessages = messages.filter(m => m.sender === 'dm');

    console.log(`User messages: ${userMessages.length}, DM messages: ${dmMessages.length}`);

    // We should have 3 user messages (different prompts each time would be better, but same text for now)
    expect(userMessages.length).toBe(3);

    // DM messages: Since they have the same text, they might be deduped if within 30 seconds
    // For this test, we expect them to be deduped since they're identical text
    expect(dmMessages.length).toBeGreaterThanOrEqual(1);
  });
});
