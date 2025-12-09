/**
 * Browser console script to test SFX WebSocket events
 *
 * Paste this into the browser console on the Player view to monitor
 * sfx_available events and audio playback.
 */

(function() {
  console.log('[SFX_DEBUG] Monitoring WebSocket events and SFX playback');

  // Monitor all audio elements
  const originalPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function() {
    console.log('[SFX_DEBUG] Audio.play() called:', {
      src: this.src?.substring(0, 100),
      currentTime: this.currentTime,
      paused: this.paused,
      muted: this.muted,
      volume: this.volume,
      readyState: this.readyState,
      className: this.className || 'no-class',
      stackTrace: new Error().stack?.split('\n').slice(1, 4).join('\n')
    });
    return originalPlay.apply(this, arguments);
  };

  // Monitor fetch requests to SFX generation API
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const url = args[0];
    if (typeof url === 'string' && url.includes('/api/sfx/generate')) {
      console.log('[SFX_DEBUG] SFX generation request:', {
        url,
        timestamp: new Date().toISOString()
      });

      return originalFetch.apply(this, args).then(response => {
        return response.clone().json().then(data => {
          console.log('[SFX_DEBUG] SFX generation response:', {
            status: response.status,
            audio: data.audio,
            timestamp: new Date().toISOString()
          });
          return response;
        }).catch(() => response);
      });
    }
    return originalFetch.apply(this, args);
  };

  // Check for SFX context
  setTimeout(() => {
    const allAudioElements = document.querySelectorAll('audio');
    console.log('[SFX_DEBUG] Found audio elements:', {
      count: allAudioElements.length,
      elements: Array.from(allAudioElements).map(a => ({
        src: a.src?.substring(0, 50),
        className: a.className,
        id: a.id,
        paused: a.paused
      }))
    });
  }, 1000);

  console.log('[SFX_DEBUG] Monitoring active. Watch for:');
  console.log('  - Audio.play() calls when you click SFX triggers');
  console.log('  - SFX generation requests and responses');
  console.log('  - WebSocket events in your browser DevTools Network tab (filter by WS)');
})();
