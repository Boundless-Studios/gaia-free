import { useState, useRef } from 'react';
import apiService from '../../services/apiService.js';
import './TurnMessage.css';

/**
 * Parse labeled inputs from combined text format.
 * Handles formats like "[PlayerName]: text" or "[DM]: text"
 * @param {string} text - Combined input text
 * @returns {Array<{label: string, text: string}>} Parsed inputs
 */
function parseInputContributions(text) {
  if (!text) return [];

  const contributions = [];
  // Match patterns like [Name]: text or [Name] (role): text
  const labelPattern = /\[([^\]]+)\](?:\s*\([^)]*\))?:\s*/g;

  let lastIndex = 0;
  let match;
  let lastLabel = null;

  while ((match = labelPattern.exec(text)) !== null) {
    // If there was text before this match without a label, add it as unlabeled
    if (lastIndex < match.index && lastLabel === null) {
      const unlabeledText = text.slice(lastIndex, match.index).trim();
      if (unlabeledText) {
        contributions.push({ label: 'Player', text: unlabeledText });
      }
    }

    // Store this label for the next segment
    if (lastLabel !== null) {
      const segmentText = text.slice(lastIndex, match.index).trim();
      if (segmentText) {
        contributions.push({ label: lastLabel, text: segmentText });
      }
    }

    lastLabel = match[1];
    lastIndex = match.index + match[0].length;
  }

  // Add the final segment
  if (lastIndex < text.length) {
    const remainingText = text.slice(lastIndex).trim();
    if (remainingText) {
      contributions.push({
        label: lastLabel || 'Player',
        text: remainingText
      });
    }
  }

  // If no labels found at all, return the whole text as a single contribution
  if (contributions.length === 0 && text.trim()) {
    contributions.push({ label: null, text: text.trim() });
  }

  return contributions;
}

/**
 * TurnMessage - Renders a single turn with input and response sections.
 *
 * A turn consists of:
 * - Input section: Active player input, observer inputs, DM additions
 * - Response section: DM's narrative response (streaming or final)
 *
 * @param {Object} turn - Turn state object from useTurnBasedMessages
 * @param {string} campaignId - Campaign/session ID
 * @param {Function} onImageGenerated - Callback when image is generated
 * @param {boolean} hideDMInput - If true, hide DM input contributions (for player view)
 */
const TurnMessage = ({
  turn,
  campaignId,
  onImageGenerated,
  hideDMInput = false,
}) => {
  const {
    turn_number,
    input,
    streamingText,
    finalMessage,
    isStreaming,
    error,
  } = turn;

  // Action button states
  const [isAudioLoading, setIsAudioLoading] = useState(false);
  const [isImageLoading, setIsImageLoading] = useState(false);
  const audioRef = useRef(null);

  // Determine what text to display
  const displayText = finalMessage?.content || streamingText || '';
  const hasContent = displayText.length > 0;

  // Format timestamp
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  // Handle audio playback
  const handleAudioPlayback = async () => {
    if (!displayText) return;

    // If already playing, stop it
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsAudioLoading(false);
      return;
    }

    try {
      setIsAudioLoading(true);

      const response = await apiService.synthesizeTTS({
        text: displayText,
        voice: 'default',
      });

      if (response?.audio?.url) {
        const audio = new Audio(response.audio.url);
        audioRef.current = audio;

        audio.onended = () => {
          audioRef.current = null;
          setIsAudioLoading(false);
        };

        audio.onerror = () => {
          console.error('Audio playback error');
          audioRef.current = null;
          setIsAudioLoading(false);
        };

        await audio.play();
      }
    } catch (err) {
      console.error('Failed to synthesize audio:', err);
      setIsAudioLoading(false);
    }
  };

  // Handle image generation
  const handleImageGeneration = async () => {
    if (!displayText) return;

    try {
      setIsImageLoading(true);

      const response = await apiService.generateImage({
        prompt: displayText,
        image_type: 'moment',
        context: displayText,
        campaign_id: campaignId,
      });

      if (response?.success && response?.image && onImageGenerated) {
        const imageData = {
          generated_image_url: response.image.image_url || response.image.url,
          generated_image_path: response.image.local_path || response.image.path,
          generated_image_prompt: response.image.prompt || response.image.original_prompt || displayText,
          generated_image_type: 'moment'
        };
        onImageGenerated(imageData);
      }

      setIsImageLoading(false);
    } catch (err) {
      console.error('Failed to generate image:', err);
      setIsImageLoading(false);
    }
  };

  // Loading spinner SVG
  const LoadingSpinner = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <circle cx="12" cy="12" r="10" strokeWidth="2" opacity="0.25"/>
      <path d="M12 2 A10 10 0 0 1 22 12" strokeWidth="2" strokeLinecap="round">
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="1s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );

  // Audio icon SVG
  const AudioIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path d="M11 5L6 9H2v6h4l5 4V5z" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );

  // Image icon SVG
  const ImageIcon = () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" strokeWidth="2"/>
      <circle cx="8.5" cy="8.5" r="1.5" strokeWidth="2"/>
      <path d="M21 15l-5-5L5 21" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );

  return (
    <div className={`turn-message ${isStreaming ? 'streaming' : ''} ${error ? 'error' : ''}`}>
      {/* Turn number indicator */}
      <div className="turn-number-badge">Turn {turn_number}</div>

      {/* Input Section - shows who contributed to this turn */}
      {input && (
        <div className="turn-input-section">
          {(() => {
            // Get the combined text to parse
            const rawText = input.combined_prompt || input.active_player?.text || '';
            let contributions = parseInputContributions(rawText);

            // Filter out DM contributions if hideDMInput is true
            if (hideDMInput) {
              contributions = contributions.filter(c => c.label !== 'DM');
            }

            // If we have parsed contributions with labels, show them
            if (contributions.length > 0 && contributions.some(c => c.label)) {
              return contributions.map((contrib, i) => (
                <div
                  key={i}
                  className={`player-input ${contrib.label === 'DM' ? 'dm-contribution' : ''}`}
                >
                  <span className={`input-label ${contrib.label === 'DM' ? 'dm-label' : ''}`}>
                    {contrib.label}:
                  </span>
                  <span className="input-text">{contrib.text}</span>
                </div>
              ));
            }

            // Fallback: show structured data if no labels in text
            // Filter out [DM]: patterns from text if hideDMInput is true
            const filterDMFromText = (text) => {
              if (!hideDMInput || !text) return text;
              // Remove [DM]: and everything after it
              return text.replace(/\[DM\](?:\s*\([^)]*\))?:\s*.*/g, '').trim();
            };

            const activePlayerText = filterDMFromText(input.active_player?.text);

            return (
              <>
                {input.active_player && activePlayerText && (
                  <div className="player-input active">
                    <span className="input-label">
                      {input.active_player.character_name || 'Player'}:
                    </span>
                    <span className="input-text">{activePlayerText}</span>
                  </div>
                )}
                {input.observer_inputs?.map((obs, i) => (
                  <div key={i} className="player-input observer">
                    <span className="input-label">
                      {obs.character_name || 'Observer'}:
                    </span>
                    <span className="input-text">{obs.text}</span>
                  </div>
                ))}
                {/* Only show DM input if not hidden */}
                {!hideDMInput && input.dm_input && input.dm_input.text && (
                  <div className="dm-input">
                    <span className="input-label">DM:</span>
                    <span className="input-text">{input.dm_input.text}</span>
                  </div>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* DM Response Section */}
      {(hasContent || isStreaming || error) && (
        <div className="dm-response-section">
          <div className="response-header">
            <span className="response-label">DM:</span>
            {finalMessage?.timestamp && (
              <span className="response-timestamp">
                {formatTime(finalMessage.timestamp)}
              </span>
            )}
            {/* Action buttons - only show when not streaming and have content */}
            {!isStreaming && hasContent && !error && (
              <div className="message-actions">
                <button
                  className={`message-action-btn audio-btn ${isAudioLoading ? 'loading' : ''}`}
                  onClick={handleAudioPlayback}
                  title="Play audio narration"
                  disabled={isAudioLoading}
                >
                  {isAudioLoading ? <LoadingSpinner /> : <AudioIcon />}
                </button>

                <button
                  className={`message-action-btn image-btn ${isImageLoading ? 'loading' : ''}`}
                  onClick={handleImageGeneration}
                  title="Generate moment image"
                  disabled={isImageLoading}
                >
                  {isImageLoading ? <LoadingSpinner /> : <ImageIcon />}
                </button>
              </div>
            )}
          </div>

          <div className="response-content">
            {error ? (
              <div className="error-message">
                Error: {error}
              </div>
            ) : (
              <>
                <span>{displayText}</span>
                {isStreaming && <span className="streaming-cursor">|</span>}
              </>
            )}
          </div>
        </div>
      )}

      {/* Processing indicator */}
      {isStreaming && !hasContent && (
        <div className="processing-indicator">
          <LoadingSpinner />
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
};

export default TurnMessage;
