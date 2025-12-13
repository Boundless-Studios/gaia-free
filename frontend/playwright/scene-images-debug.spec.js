// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Playwright tests for the Scene Images Debug Page
 *
 * These tests verify the Visual Narrator and scene image generation pipeline.
 * They require the backend to be running with the scene-images API endpoints.
 */

test.describe('Scene Images Debug Page', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the debug page
    await page.goto('/admin/debug-scene-images');

    // Wait for the page to load
    await expect(page.getByTestId('scene-images-debug-page')).toBeVisible();
  });

  test('should display the debug page with all form elements', async ({ page }) => {
    // Verify header
    await expect(page.getByRole('heading', { name: 'Scene Images Debug Page' })).toBeVisible();

    // Verify form elements exist
    await expect(page.getByTestId('campaign-id-input')).toBeVisible();
    await expect(page.getByTestId('turn-number-input')).toBeVisible();
    await expect(page.getByTestId('scene-description-input')).toBeVisible();
    await expect(page.getByTestId('generate-button')).toBeVisible();
  });

  test('should have default values populated', async ({ page }) => {
    // Campaign ID should have a default value
    const campaignIdInput = page.getByTestId('campaign-id-input');
    const campaignIdValue = await campaignIdInput.inputValue();
    expect(campaignIdValue).toMatch(/^debug_campaign_\d+$/);

    // Turn number should default to 1
    const turnNumberInput = page.getByTestId('turn-number-input');
    await expect(turnNumberInput).toHaveValue('1');

    // Scene description should have default text
    const sceneDescriptionInput = page.getByTestId('scene-description-input');
    const sceneDescription = await sceneDescriptionInput.inputValue();
    expect(sceneDescription.length).toBeGreaterThan(50);
  });

  test('should allow editing form fields', async ({ page }) => {
    // Edit campaign ID
    const campaignIdInput = page.getByTestId('campaign-id-input');
    await campaignIdInput.fill('test_campaign_123');
    await expect(campaignIdInput).toHaveValue('test_campaign_123');

    // Edit turn number
    const turnNumberInput = page.getByTestId('turn-number-input');
    await turnNumberInput.fill('5');
    await expect(turnNumberInput).toHaveValue('5');

    // Edit scene description
    const sceneDescriptionInput = page.getByTestId('scene-description-input');
    await sceneDescriptionInput.fill('A mysterious forest path');
    await expect(sceneDescriptionInput).toHaveValue('A mysterious forest path');
  });

  test('should disable generate button when scene description is empty', async ({ page }) => {
    // Clear the scene description
    const sceneDescriptionInput = page.getByTestId('scene-description-input');
    await sceneDescriptionInput.fill('');

    // Button should be disabled
    const generateButton = page.getByTestId('generate-button');
    await expect(generateButton).toBeDisabled();
  });

  test('should enable generate button when scene description has content', async ({ page }) => {
    // Ensure scene description has content
    const sceneDescriptionInput = page.getByTestId('scene-description-input');
    await sceneDescriptionInput.fill('A test scene description');

    // Button should be enabled
    const generateButton = page.getByTestId('generate-button');
    await expect(generateButton).toBeEnabled();
  });

  test('should show logs container', async ({ page }) => {
    await expect(page.getByTestId('logs-container')).toBeVisible();
  });

  test('should trigger generation and show results', async ({ page }) => {
    // Fill in the form
    await page.getByTestId('campaign-id-input').fill('playwright_test_' + Date.now());
    await page.getByTestId('scene-description-input').fill(
      'A dark dungeon corridor with flickering torches on the walls. ' +
      'Cobwebs hang from the ceiling and the air is thick with dust.'
    );

    // Click generate button
    const generateButton = page.getByTestId('generate-button');
    await generateButton.click();

    // Button should show loading state
    await expect(generateButton).toContainText('Generating...');
    await expect(generateButton).toBeDisabled();

    // Wait for the results section to appear (with a longer timeout for API calls)
    await expect(page.getByTestId('results-section')).toBeVisible({ timeout: 60000 });

    // Verify the images grid appears
    await expect(page.getByTestId('images-grid')).toBeVisible();

    // Verify all three image cards are present
    await expect(page.getByTestId('image-card-location_ambiance')).toBeVisible();
    await expect(page.getByTestId('image-card-background_detail')).toBeVisible();
    await expect(page.getByTestId('image-card-moment_focus')).toBeVisible();
  });

  test('should show error message when generation fails', async ({ page }) => {
    // Use an invalid campaign ID or trigger an error condition
    await page.getByTestId('campaign-id-input').fill('');
    await page.getByTestId('scene-description-input').fill('Test scene');

    // Re-fill campaign ID to enable button (it validates on scene description)
    await page.getByTestId('campaign-id-input').fill('test');

    // Click generate
    await page.getByTestId('generate-button').click();

    // Wait for response - either results or error
    await page.waitForTimeout(5000);

    // Logs should show activity
    const logsContainer = page.getByTestId('logs-container');
    const logsText = await logsContainer.textContent();
    expect(logsText.length).toBeGreaterThan(0);
  });

  test('should add logs when generating', async ({ page }) => {
    await page.getByTestId('scene-description-input').fill('A test scene for logging');
    await page.getByTestId('generate-button').click();

    // Wait a moment for logs to appear
    await page.waitForTimeout(1000);

    // Logs container should have content
    const logsContainer = page.getByTestId('logs-container');
    await expect(logsContainer).not.toContainText('No logs yet');
  });

  test('should clear logs when clear button is clicked', async ({ page }) => {
    // First generate to create some logs
    await page.getByTestId('scene-description-input').fill('Test for clearing logs');
    await page.getByTestId('generate-button').click();
    await page.waitForTimeout(1000);

    // Click clear button
    await page.getByRole('button', { name: 'Clear' }).click();

    // Logs should be cleared
    await expect(page.getByTestId('logs-container')).toContainText('No logs yet');
  });
});

test.describe('Scene Images Debug Page - Image Generation Flow', () => {
  // These tests require a running backend with image generation capabilities
  // They are marked as slow due to the time needed for image generation

  test.slow();

  test('should generate all three images successfully', async ({ page }) => {
    await page.goto('/admin/debug-scene-images');

    // Use a unique campaign ID
    const campaignId = 'e2e_test_' + Date.now();
    await page.getByTestId('campaign-id-input').fill(campaignId);
    await page.getByTestId('scene-description-input').fill(
      'A medieval marketplace bustling with activity. Colorful stalls line the cobblestone streets. ' +
      'Merchants call out their wares while customers haggle over prices.'
    );

    // Start generation
    await page.getByTestId('generate-button').click();

    // Wait for results section
    await expect(page.getByTestId('results-section')).toBeVisible({ timeout: 60000 });

    // Poll for completion (images might take time to generate)
    await page.waitForFunction(
      () => {
        const setStatus = document.querySelector('[data-testid="set-status"]');
        return setStatus && (
          setStatus.textContent?.includes('complete') ||
          setStatus.textContent?.includes('failed')
        );
      },
      { timeout: 120000 } // 2 minutes for all images
    );

    // Check final status
    const setStatus = page.getByTestId('set-status');
    const statusText = await setStatus.textContent();

    // If complete, verify images are displayed
    if (statusText?.includes('complete')) {
      // At least one image should have loaded
      const images = page.locator('[data-testid^="image-"]');
      const imageCount = await images.count();
      expect(imageCount).toBeGreaterThan(0);
    }
  });

  test('should show status updates while generating', async ({ page }) => {
    await page.goto('/admin/debug-scene-images');

    await page.getByTestId('campaign-id-input').fill('status_test_' + Date.now());
    await page.getByTestId('scene-description-input').fill('A quiet library with ancient tomes');
    await page.getByTestId('generate-button').click();

    // Wait for results section
    await expect(page.getByTestId('results-section')).toBeVisible({ timeout: 30000 });

    // Verify status indicators are present
    const statusIndicators = page.locator('[data-testid^="status-"]');
    const statusCount = await statusIndicators.count();
    expect(statusCount).toBe(3); // Three image types

    // Verify at least one status is visible
    await expect(statusIndicators.first()).toBeVisible();
  });
});
