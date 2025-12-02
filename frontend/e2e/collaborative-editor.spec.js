import { test, expect } from '@playwright/test';

test.describe('Collaborative CodeMirror Editor', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the collaborative editor test page
    await page.goto('/test/collaborative-editor');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Wait for editors to initialize
    await page.waitForTimeout(1000);
  });

  test('should initialize 4 player editors', async ({ page }) => {
    // Check that all 4 player panels are present
    const playerPanels = await page.locator('.editor-panel').all();
    expect(playerPanels.length).toBe(4);

    // Verify player names
    const playerNames = await page.locator('.editor-panel-header h3').allTextContents();
    expect(playerNames).toEqual(['Aragorn', 'Gandalf', 'Legolas', 'Gimli']);

    // Check that all editors have CodeMirror initialized
    const editors = await page.locator('.cm-editor').all();
    expect(editors.length).toBe(4);

    // Verify all editors show as connected
    const connectionStatuses = await page.locator('.connection-status .status-text').allTextContents();
    connectionStatuses.forEach(status => {
      expect(status.trim()).toBe('Connected');
    });
  });

  test('should show active turn badge for current player', async ({ page }) => {
    // Check that first player (Aragorn) has active turn initially
    const firstPanel = page.locator('.editor-panel').first();
    await expect(firstPanel.locator('.active-turn-badge')).toBeVisible();
    await expect(firstPanel.locator('.turn-badge')).toContainText('Your Turn');

    // Verify submit button is only visible for active player
    const submitButtons = await page.locator('.submit-button').all();
    expect(submitButtons.length).toBe(1);

    // Other players should show waiting message
    const waitingMessages = await page.locator('.waiting-message').all();
    expect(waitingMessages.length).toBe(3);
  });

  test('should sync text across all editors in real-time', async ({ page }) => {
    // Get all editors
    const editors = await page.locator('.cm-editor').all();

    // Focus and type in the first editor (Aragorn - active player)
    await editors[0].click();
    await page.keyboard.type('Hello from Aragorn');

    // Wait for sync
    await page.waitForTimeout(300);

    // Verify text appears in all 4 editors
    for (let i = 0; i < 4; i++) {
      const editorText = await editors[i].locator('.cm-content').textContent();
      expect(editorText.trim()).toBe('Hello from Aragorn');
    }
  });

  test('should sync text when typing in non-active editor', async ({ page }) => {
    // Get all editors
    const editors = await page.locator('.cm-editor').all();

    // Type in second editor (Gandalf - NOT active player)
    await editors[1].click();
    await page.keyboard.type('Gandalf types here');

    // Wait for sync
    await page.waitForTimeout(300);

    // Verify text appears in all editors including active one
    for (let i = 0; i < 4; i++) {
      const editorText = await editors[i].locator('.cm-content').textContent();
      expect(editorText.trim()).toBe('Gandalf types here');
    }
  });

  test('should handle simultaneous typing without data loss', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type in first editor
    await editors[0].click();
    await page.keyboard.type('First ');

    // Immediately type in second editor
    await editors[1].click();
    await page.keyboard.type('Second ');

    // Type in third editor
    await editors[2].click();
    await page.keyboard.type('Third');

    // Wait for CRDT to resolve conflicts
    await page.waitForTimeout(500);

    // Check that all text is present in all editors (Yjs CRDT should merge)
    for (let i = 0; i < 4; i++) {
      const editorText = await editors[i].locator('.cm-content').textContent();
      // Text should contain all three inputs (order may vary due to CRDT)
      expect(editorText).toContain('First');
      expect(editorText).toContain('Second');
      expect(editorText).toContain('Third');
    }
  });

  test('should advance turn when active player submits', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type text as Aragorn (active player)
    await editors[0].click();
    await page.keyboard.type('Aragorn submits this text');

    // Wait for sync
    await page.waitForTimeout(200);

    // Find and click submit button
    const submitButton = page.locator('.submit-button').first();
    await submitButton.click();

    // Wait for submission and turn advance
    await page.waitForTimeout(300);

    // Verify text was cleared after submission
    const editorText = await editors[0].locator('.cm-content').textContent();
    expect(editorText.trim()).toBe('');

    // Verify turn advanced to next player (Gandalf)
    const secondPanel = page.locator('.editor-panel').nth(1);
    await expect(secondPanel.locator('.active-turn-badge')).toBeVisible();

    // Verify submission appears in history
    const submissionHistory = page.locator('.submission-history');
    await expect(submissionHistory).toBeVisible();
    await expect(submissionHistory.locator('.submission-card')).toContainText('Aragorn');
    await expect(submissionHistory.locator('.submission-text')).toContainText('Aragorn submits this text');
  });

  test('should only allow active player to submit', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type in first editor (Aragorn - active)
    await editors[0].click();
    await page.keyboard.type('Active player text');

    // Check submit button exists for Aragorn
    const firstPanel = page.locator('.editor-panel').first();
    await expect(firstPanel.locator('.submit-button')).toBeVisible();

    // Check submit button does NOT exist for Gandalf (not active)
    const secondPanel = page.locator('.editor-panel').nth(1);
    await expect(secondPanel.locator('.submit-button')).not.toBeVisible();
    await expect(secondPanel.locator('.waiting-message')).toBeVisible();
  });

  test('should support keyboard shortcut (Ctrl+Enter) for submission', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type text as Aragorn
    await editors[0].click();
    await page.keyboard.type('Submitting with keyboard');

    // Wait for sync
    await page.waitForTimeout(200);

    // Press Ctrl+Enter to submit
    await page.keyboard.press('Control+Enter');

    // Wait for submission
    await page.waitForTimeout(300);

    // Verify text was cleared
    const editorText = await editors[0].locator('.cm-content').textContent();
    expect(editorText.trim()).toBe('');

    // Verify submission in history
    await expect(page.locator('.submission-history')).toBeVisible();
    await expect(page.locator('.submission-text')).toContainText('Submitting with keyboard');
  });

  test('should use Next Turn button to manually advance', async ({ page }) => {
    // Click Next Turn button
    const nextTurnButton = page.getByRole('button', { name: 'Next Turn' });
    await nextTurnButton.click();

    // Wait for turn change
    await page.waitForTimeout(200);

    // Verify second player (Gandalf) now has active turn
    const secondPanel = page.locator('.editor-panel').nth(1);
    await expect(secondPanel.locator('.active-turn-badge')).toBeVisible();

    // Verify current turn info updated
    const turnInfo = page.locator('.current-turn-info');
    await expect(turnInfo).toContainText('Gandalf');
  });

  test('should clear text with Clear Text button', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type text
    await editors[0].click();
    await page.keyboard.type('Text to be cleared');

    // Wait for sync
    await page.waitForTimeout(200);

    // Verify text exists in all editors
    for (const editor of editors) {
      const text = await editor.locator('.cm-content').textContent();
      expect(text).toContain('Text to be cleared');
    }

    // Click Clear Text button
    const clearButton = page.getByRole('button', { name: 'Clear Text' });
    await clearButton.click();

    // Wait for clear to propagate
    await page.waitForTimeout(300);

    // Verify all editors are empty
    for (const editor of editors) {
      const text = await editor.locator('.cm-content').textContent();
      expect(text.trim()).toBe('');
    }
  });

  test('should display submission history chronologically', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // First submission - Aragorn
    await editors[0].click();
    await page.keyboard.type('First submission');
    await page.keyboard.press('Control+Enter');
    await page.waitForTimeout(300);

    // Second submission - Gandalf
    await editors[1].click();
    await page.keyboard.type('Second submission');
    await page.keyboard.press('Control+Enter');
    await page.waitForTimeout(300);

    // Third submission - Legolas
    await editors[2].click();
    await page.keyboard.type('Third submission');
    await page.keyboard.press('Control+Enter');
    await page.waitForTimeout(300);

    // Check submission history
    const submissions = await page.locator('.submission-card').all();
    expect(submissions.length).toBe(3);

    // Verify chronological order
    const submissionTexts = await page.locator('.submission-text').allTextContents();
    expect(submissionTexts[0].trim()).toBe('First submission');
    expect(submissionTexts[1].trim()).toBe('Second submission');
    expect(submissionTexts[2].trim()).toBe('Third submission');

    // Verify player names
    const playerNames = await page.locator('.submission-card .submission-header strong').allTextContents();
    expect(playerNames).toEqual(['Aragorn', 'Gandalf', 'Legolas']);
  });

  test('should prevent empty submissions', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Focus editor but don't type anything
    await editors[0].click();

    // Try to submit empty content
    await page.keyboard.press('Control+Enter');

    // Wait
    await page.waitForTimeout(300);

    // Verify no submission was created
    const submissionHistory = page.locator('.submission-history');
    await expect(submissionHistory).not.toBeVisible();
  });

  test('should handle line breaks and formatting', async ({ page }) => {
    const editors = await page.locator('.cm-editor').all();

    // Type multi-line text
    await editors[0].click();
    await page.keyboard.type('Line 1');
    await page.keyboard.press('Enter');
    await page.keyboard.type('Line 2');
    await page.keyboard.press('Enter');
    await page.keyboard.type('Line 3');

    // Wait for sync
    await page.waitForTimeout(300);

    // Verify all editors have multi-line content
    for (const editor of editors) {
      const text = await editor.locator('.cm-content').textContent();
      expect(text).toContain('Line 1');
      expect(text).toContain('Line 2');
      expect(text).toContain('Line 3');
    }
  });

  test('should maintain connection status indicator', async ({ page }) => {
    // All editors should show connected status
    const statusDots = await page.locator('.status-dot').all();
    expect(statusDots.length).toBe(4);

    for (const dot of statusDots) {
      const classes = await dot.getAttribute('class');
      expect(classes).toContain('connected');
    }

    // All status texts should say "Connected"
    const statusTexts = await page.locator('.status-text').allTextContents();
    statusTexts.forEach(text => {
      expect(text.trim()).toBe('Connected');
    });
  });

  test('should show keyboard hint for submit shortcut', async ({ page }) => {
    // First editor (Aragorn - active) should show keyboard hint
    const firstPanel = page.locator('.editor-panel').first();
    await expect(firstPanel.locator('.keyboard-hint')).toBeVisible();
    await expect(firstPanel.locator('.keyboard-hint')).toContainText('Ctrl+Enter');

    // Other editors should not show the hint (they show waiting message instead)
    const secondPanel = page.locator('.editor-panel').nth(1);
    await expect(secondPanel.locator('.keyboard-hint')).not.toBeVisible();
  });
});
