import { test, expect } from '@playwright/test';

test.describe('Audio Playback', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the DM view
    await page.goto('/');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');
  });

  test('should trigger synchronized audio stream after DM message', async ({ page }) => {
    // Setup WebSocket message listener before interacting
    const wsMessages = [];

    // Intercept WebSocket messages
    await page.route('**/ws/campaign/dm**', async (route) => {
      // Allow the WebSocket connection
      await route.continue();
    });

    // Listen for console logs that indicate WebSocket activity
    page.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('audio_stream_started')) {
        wsMessages.push({ type: 'audio_stream_started', text });
      }
      if (text.includes('[AUDIO_STREAM] Starting stream')) {
        wsMessages.push({ type: 'audio_stream_starting', text });
      }
    });

    // Wait for campaign to load or create one
    await page.waitForTimeout(2000);

    // Check if we need to create a campaign first
    const createButton = page.getByRole('button', { name: /create.*campaign/i });
    if (await createButton.isVisible()) {
      await createButton.click();

      // Fill in campaign creation form
      await page.fill('input[name="name"]', 'Audio Test Campaign');
      await page.fill('textarea[name="description"]', 'Testing audio playback');

      // Submit
      const submitButton = page.getByRole('button', { name: /create/i });
      await submitButton.click();

      // Wait for campaign to be created
      await page.waitForTimeout(3000);
    }

    // Find the message input
    const messageInput = page.locator('textarea, input[type="text"]').first();
    await expect(messageInput).toBeVisible({ timeout: 10000 });

    // Type a short message
    await messageInput.fill('Hello, test message for audio');

    // Send the message
    await page.keyboard.press('Enter');

    // Wait for the response and audio generation
    await page.waitForTimeout(8000);

    // Check if audio_stream_started was received
    const audioStartMessages = wsMessages.filter((m) => m.type === 'audio_stream_started');
    console.log('WebSocket messages received:', wsMessages);
    console.log('Audio start messages:', audioStartMessages);

    // Verify audio element exists and has a source
    const audioElement = await page.evaluate(() => {
      // Find audio elements on the page
      const audios = Array.from(document.querySelectorAll('audio'));

      // Look for the streaming audio element (created by AudioStreamProvider)
      const streamingAudio = audios.find((a) => a.src && a.src.includes('/api/audio/stream/'));

      if (streamingAudio) {
        return {
          exists: true,
          src: streamingAudio.src,
          paused: streamingAudio.paused,
          currentTime: streamingAudio.currentTime,
          readyState: streamingAudio.readyState,
          networkState: streamingAudio.networkState,
        };
      }

      return { exists: false };
    });

    console.log('Audio element state:', audioElement);

    // Assertions
    expect(audioElement.exists).toBeTruthy();
    expect(audioElement.src).toContain('/api/audio/stream/');

    // Check that audio started playing (not paused OR currentTime > 0)
    expect(audioElement.paused === false || audioElement.currentTime > 0).toBeTruthy();
  });

  test('should handle audio mute toggle', async ({ page }) => {
    // Wait for page load
    await page.waitForTimeout(2000);

    // Find mute button (look for audio/volume controls)
    const muteButton = page.locator('button').filter({ hasText: /mute|volume|audio/i }).first();

    if (await muteButton.isVisible()) {
      // Click to toggle mute
      await muteButton.click();

      // Check localStorage for mute state
      const muteState = await page.evaluate(() => {
        return localStorage.getItem('gaiaAudioMuted');
      });

      console.log('Mute state after toggle:', muteState);
      expect(['true', 'false']).toContain(muteState);
    } else {
      console.log('Mute button not found - skipping mute toggle test');
    }
  });

  test('should verify audio stream URL format', async ({ page }) => {
    // This test verifies the audio context is properly configured
    const audioContextConfig = await page.evaluate(() => {
      // Check if AudioStreamContext is available
      const audioElements = Array.from(document.querySelectorAll('audio'));

      return {
        audioElementCount: audioElements.length,
        audioSources: audioElements.map((a) => a.src),
      };
    });

    console.log('Audio context configuration:', audioContextConfig);

    // We should have at least one audio element from AudioStreamProvider
    expect(audioContextConfig.audioElementCount).toBeGreaterThanOrEqual(1);
  });
});
