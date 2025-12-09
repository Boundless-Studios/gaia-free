import React, { useCallback, useState } from 'react';
import { useSFX } from '../context/sfxContext.jsx';
import './SFXTrigger.css';

/**
 * SFXTrigger Component
 *
 * Renders a clickable span with dotted underline that generates
 * and plays sound effects when clicked.
 *
 * Props:
 * - phrase: The text to display and send to the SFX API
 * - sfxId: Optional catalog ID for caching
 * - sessionId: Current game session ID
 */
const SFXTrigger = ({ phrase, sfxId = null, sessionId }) => {
  const { generateSoundEffect, playSfxFromPayload, getCachedSFX, isGenerating: contextIsGenerating } = useSFX();
  const [isGenerating, setIsGenerating] = useState(false);

  const handleClick = useCallback(async (e) => {
    e.preventDefault();
    e.stopPropagation();

    if (isGenerating || contextIsGenerating) {
      return;
    }

    try {
      // Check cache first
      const cached = getCachedSFX?.(sfxId, phrase);

      if (cached) {
        console.log('[SFXTrigger] Playing cached SFX:', phrase);
        await playSfxFromPayload(cached);
        return;
      }

      // Generate new SFX
      console.log('[SFXTrigger] Generating SFX for:', phrase);
      setIsGenerating(true);

      const result = await generateSoundEffect(phrase, sessionId, sfxId);

      if (result?.audio) {
        console.log('[SFXTrigger] SFX generated successfully');
        // The generateSoundEffect already caches the result
        // It will also be broadcast via WebSocket, so other clients will receive it
      } else {
        console.warn('[SFXTrigger] No audio returned from generation');
      }
    } catch (error) {
      console.error('[SFXTrigger] Failed to generate SFX:', error);
    } finally {
      setIsGenerating(false);
    }
  }, [phrase, sfxId, sessionId, generateSoundEffect, playSfxFromPayload, getCachedSFX, isGenerating, contextIsGenerating]);

  const className = `sfx-trigger${isGenerating ? ' sfx-trigger--generating' : ''}`;

  return (
    <span
      className={className}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          handleClick(e);
        }
      }}
      title={`Click to generate sound effect: ${phrase}`}
      aria-label={`Generate sound effect for: ${phrase}`}
    >
      {phrase}
    </span>
  );
};

export default SFXTrigger;
