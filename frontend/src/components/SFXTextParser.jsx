import React, { useMemo } from 'react';
import { detectSFXPhrases } from '../services/sfxDetector.js';
import SFXTrigger from './SFXTrigger.jsx';

/**
 * SFXTextParser Component
 *
 * Parses narrative text to detect SFX-worthy phrases and renders them
 * as clickable SFXTrigger components interleaved with plain text.
 *
 * Props:
 * - text: The narrative text to parse
 * - sessionId: Current game session ID for SFX generation
 */
const SFXTextParser = ({ text, sessionId }) => {
  // Memoize the parsed content to avoid re-parsing on every render
  const parsedContent = useMemo(() => {
    if (!text || typeof text !== 'string') {
      console.log('[SFXTextParser] No valid text provided:', typeof text);
      return text;
    }

    console.log('[SFXTextParser] Parsing text:', text.substring(0, 100) + '...');

    // Detect SFX phrases in the text
    const detectedPhrases = detectSFXPhrases(text);

    console.log('[SFXTextParser] Detected phrases:', detectedPhrases);

    if (detectedPhrases.length === 0) {
      // No SFX detected, return text as-is
      console.log('[SFXTextParser] No SFX phrases detected');
      return text;
    }

    // Build an array of text segments and SFX triggers
    const segments = [];
    let lastIndex = 0;

    for (const match of detectedPhrases) {
      // Add plain text before this match
      if (match.startIdx > lastIndex) {
        const plainText = text.substring(lastIndex, match.startIdx);
        if (plainText) {
          segments.push(
            <React.Fragment key={`text-${lastIndex}`}>
              {plainText}
            </React.Fragment>
          );
        }
      }

      // Add SFXTrigger for this match
      segments.push(
        <SFXTrigger
          key={`sfx-${match.startIdx}-${match.endIdx}`}
          phrase={match.phrase}
          sfxId={match.sfxId}
          category={match.category}
          sessionId={sessionId}
        />
      );

      lastIndex = match.endIdx;
    }

    // Add remaining text after last match
    if (lastIndex < text.length) {
      const remainingText = text.substring(lastIndex);
      if (remainingText) {
        segments.push(
          <React.Fragment key={`text-${lastIndex}`}>
            {remainingText}
          </React.Fragment>
        );
      }
    }

    return segments;
  }, [text, sessionId]);

  return <>{parsedContent}</>;
};

// Memoize the component to prevent unnecessary re-renders
export default React.memo(SFXTextParser);
