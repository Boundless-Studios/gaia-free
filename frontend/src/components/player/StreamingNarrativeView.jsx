import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import './StreamingNarrativeView.css';
import apiService from '../../services/apiService.js';
import { useLoading, LoadingTypes } from '../../contexts/LoadingContext';
import SFXTextParser from '../SFXTextParser.jsx';

/**
 * StreamingNarrativeView - Displays message history and current streaming DM narrative
 *
 * Shows:
 * 1. Previous messages with Player/DM labels and timestamps
 * 2. Current streaming content (narrative + player response)
 * 3. Streaming indicators
 * 4. Scroll indicator when there's more content below
 *
 * Scroll behavior: Shows the top of the latest message by default
 */
const StreamingNarrativeView = ({
  narrative,
  playerResponse,
  isNarrativeStreaming,
  isResponseStreaming,
  messages = [],
  onImageGenerated,
  campaignId,
}) => {
  // Debug: Log only when messages change (not during streaming)
  // Uncomment for detailed debugging:
  // console.log('📜 StreamingNarrativeView render:', { messagesCount: messages.length });

  // Check if streaming content already exists in message history to prevent duplicates
  const streamingTextNormalized = (narrative || playerResponse || '').replace(/\s+/g, ' ').trim();
  const streamingAlreadyInHistory = useMemo(() => {
    if (!streamingTextNormalized) return false;
    return messages.some(msg => {
      if (msg.sender !== 'dm') return false;
      const msgText = (msg.text || '').replace(/\s+/g, ' ').trim();
      return msgText === streamingTextNormalized;
    });
  }, [messages, streamingTextNormalized]);

  const hasStreamingContent = (narrative || playerResponse) && !streamingAlreadyInHistory;
  const containerRef = useRef(null);
  const latestMessageRef = useRef(null);
  const streamingContentRef = useRef(null);
  const [showScrollIndicator, setShowScrollIndicator] = useState(false);
  const { setLoading } = useLoading();

  // Track loading states for each message
  const [audioLoadingStates, setAudioLoadingStates] = useState({});
  const [imageLoadingStates, setImageLoadingStates] = useState({});
  const audioRefs = useRef({});

  const orderedMessages = useMemo(() => {
    if (!Array.isArray(messages)) {
      return [];
    }

    const getOrder = (msg, index) =>
      typeof msg?.clientOrder === 'number' ? msg.clientOrder : index;

    return [...messages]
      .map((msg, index) => ({
        msg,
        order: getOrder(msg, index),
        index,
      }))
      .sort((a, b) => {
        if (a.order !== b.order) {
          return a.order - b.order;
        }
        return a.index - b.index;
      })
      .map(({ msg }) => msg);
  }, [messages]);

  // Format timestamp to readable time
  const formatTime = (timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  // Check if user is at the bottom of the scroll container
  const checkScrollPosition = useCallback(() => {
    if (!containerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100; // Within 100px of bottom

    setShowScrollIndicator(!isNearBottom);
  }, []);

  const scrollToBottom = useCallback((options = {}) => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const behavior = options.behavior || 'smooth';

    if (typeof container.scrollTo === 'function') {
      container.scrollTo({
        top: container.scrollHeight,
        behavior
      });
    } else {
      container.scrollTop = container.scrollHeight;
    }
  }, []);

  // Ensure the latest message stays anchored at the bottom when new content arrives
  useEffect(() => {
    // Wait for DOM to paint before scrolling to avoid race conditions
    requestAnimationFrame(() => {
      scrollToBottom({ behavior: 'smooth' });

      setTimeout(checkScrollPosition, 500);
    });
  }, [
    orderedMessages.length,
    narrative,
    playerResponse,
    checkScrollPosition,
    scrollToBottom
  ]);

  // Add scroll listener to track position
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('scroll', checkScrollPosition);

    // Initial check
    checkScrollPosition();

    return () => {
      container.removeEventListener('scroll', checkScrollPosition);
    };
  }, [checkScrollPosition]);

  // Scroll to bottom when indicator is clicked
  const handleScrollIndicatorClick = () => {
    scrollToBottom({ behavior: 'smooth' });
  };

  const getMessageLabel = (msg) => {
    const sender = msg?.sender;

    if (sender === 'dm') {
      return 'DM:';
    }

    if (sender === 'system') {
      return 'SYSTEM:';
    }

    if (sender === 'user') {
      const explicitName =
        msg.characterName ||
        msg.character_name ||
        msg.playerName ||
        msg.player_name ||
        msg.displayName ||
        msg.display_name ||
        msg.character?.display_name ||
        msg.character?.name ||
        msg.character_id ||
        (msg.metadata?.character_name || msg.metadata?.characterName) ||
        (msg.metadata?.character?.display_name || msg.metadata?.character?.name) ||
        msg.metadata?.player_name ||
        msg.metadata?.playerName ||
        null;

      return `${explicitName || 'Player'}:`;
    }

    if (sender) {
      return `${String(sender).toUpperCase()}:`;
    }

    return 'PLAYER:';
  };

  // Handle audio playback for a message
  const handleAudioPlayback = async (msg) => {
    const messageId = msg.id || msg.message_id;
    if (!messageId || !msg.text) return;

    // If already playing, stop it
    if (audioRefs.current[messageId]) {
      audioRefs.current[messageId].pause();
      audioRefs.current[messageId] = null;
      setAudioLoadingStates(prev => ({ ...prev, [messageId]: false }));
      return;
    }

    try {
      setAudioLoadingStates(prev => ({ ...prev, [messageId]: true }));

      // Synthesize TTS for the message
      const response = await apiService.synthesizeTTS({
        text: msg.text,
        voice: 'default', // Use default narrator voice
      });

      if (response?.audio?.url) {
        // Create and play audio
        const audio = new Audio(response.audio.url);
        audioRefs.current[messageId] = audio;

        audio.onended = () => {
          audioRefs.current[messageId] = null;
          setAudioLoadingStates(prev => ({ ...prev, [messageId]: false }));
        };

        audio.onerror = () => {
          console.error('Audio playback error');
          audioRefs.current[messageId] = null;
          setAudioLoadingStates(prev => ({ ...prev, [messageId]: false }));
        };

        await audio.play();
      }
    } catch (error) {
      console.error('Failed to synthesize audio:', error);
      setAudioLoadingStates(prev => ({ ...prev, [messageId]: false }));
    }
  };

  // Handle moment image generation
  const handleImageGeneration = async (msg) => {
    const messageId = msg.id || msg.message_id;
    if (!messageId || !msg.text) return;

    try {
      setImageLoadingStates(prev => ({ ...prev, [messageId]: true }));

      // Generate moment image for the message
      const response = await apiService.generateImage({
        prompt: msg.text,
        image_type: 'moment',
        context: msg.text,
        campaign_id: campaignId,
      });

      console.log('Image generation response:', response);

      // Format and send to gallery if successful
      if (response?.success && response?.image && onImageGenerated) {
        const imageData = {
          generated_image_url: response.image.image_url || response.image.url,
          generated_image_path: response.image.local_path || response.image.path,
          generated_image_prompt: response.image.prompt || response.image.original_prompt || msg.text,
          generated_image_type: 'moment'
        };
        console.log('StreamingNarrativeView - formatted imageData:', imageData);
        onImageGenerated(imageData);
      }

      setImageLoadingStates(prev => ({ ...prev, [messageId]: false }));
    } catch (error) {
      console.error('Failed to generate image:', error);
      setImageLoadingStates(prev => ({ ...prev, [messageId]: false }));
    }
  };

  return (
    <div className="streaming-narrative-container" ref={containerRef}>
      {/* Message History */}
      {orderedMessages.length > 0 && (
        <div className="message-history">
          {orderedMessages.map((msg, index) => {
            const messageId = msg.id || msg.message_id || index;
            const isAudioLoading = audioLoadingStates[messageId];
            const isImageLoading = imageLoadingStates[messageId];
            const isDM = msg.sender === 'dm';

            return (
              <div
                key={msg.id || index}
                className={`message-entry ${msg.sender}`}
                ref={index === orderedMessages.length - 1 ? latestMessageRef : null}
              >
                <div className="message-header">
                  <span className="message-label">
                    {getMessageLabel(msg)}
                  </span>
                  <div className="message-header-right">
                    <span className="message-timestamp">
                      {formatTime(msg.timestamp)}
                    </span>
                    {/* Action buttons - only for DM messages */}
                    {isDM && (
                      <div className="message-actions">
                        {/* Audio playback button */}
                        <button
                          className={`message-action-btn audio-btn ${isAudioLoading ? 'loading' : ''}`}
                          onClick={() => handleAudioPlayback(msg)}
                          title="Play audio narration"
                          disabled={isAudioLoading}
                        >
                          {isAudioLoading ? (
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
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                              <path d="M11 5L6 9H2v6h4l5 4V5z" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </button>

                        {/* Image generation button */}
                        <button
                          className={`message-action-btn image-btn ${isImageLoading ? 'loading' : ''}`}
                          onClick={() => handleImageGeneration(msg)}
                          title="Generate moment image"
                          disabled={isImageLoading}
                        >
                          {isImageLoading ? (
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
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                              <rect x="3" y="3" width="18" height="18" rx="2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              <circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"/>
                              <path d="M21 15l-5-5L5 21" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="message-text">
                  {msg.sender === 'dm' && typeof msg.text === 'string' ? (
                    <SFXTextParser
                      text={msg.text}
                      sessionId={campaignId}
                    />
                  ) : (
                    msg.text
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Current Streaming Content - show until explicitly cleared by history reload */}
      {hasStreamingContent && (
        <div className="streaming-content" ref={streamingContentRef}>
          {/* Narrative Section - Atmospheric Scene Description */}
          {narrative && (
            <div className="narrative-section">
              <h3 className="narrative-header">DM:</h3>
              <div className="narrative-content">
                <SFXTextParser
                  text={narrative}
                  sessionId={campaignId}
                />
                {isNarrativeStreaming && <span className="streaming-cursor">▮</span>}
              </div>
            </div>
          )}

          {/* Player Response Section - Direct Answer/Consequences */}
          {playerResponse && (
            <div className="response-section">
              <div className="response-content">
                {playerResponse}
                {isResponseStreaming && <span className="streaming-cursor">▮</span>}
              </div>
            </div>
          )}

          {/* Streaming Indicator - Show when any streaming is in progress */}
          {(isNarrativeStreaming || isResponseStreaming) && (
            <div className="streaming-indicator">
              <div className="streaming-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
              <span className="streaming-text">
                {isNarrativeStreaming ? 'DM is setting the scene...' : 'DM is responding...'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Scroll to bottom indicator - only show when there are messages */}
      {showScrollIndicator && orderedMessages.length > 0 && (
        <button
          className="scroll-to-bottom-indicator"
          onClick={handleScrollIndicatorClick}
          aria-label="Scroll to bottom"
          title="More content below"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M7 10L12 15L17 10"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      )}
    </div>
  );
};

export default StreamingNarrativeView;
