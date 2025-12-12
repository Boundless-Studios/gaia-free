import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import './StreamingNarrativeView.css';
import TurnMessage from './TurnMessage.jsx';

/**
 * TurnBasedNarrativeView - Displays message history using turn-based ordering
 *
 * This is a drop-in replacement for StreamingNarrativeView that uses the
 * turn-based message architecture for proper message ordering.
 *
 * Receives turns from parent (App.jsx manages state via WebSocket turn events).
 *
 * Features:
 * 1. Groups messages into turns (player input + DM response)
 * 2. Shows streaming content within the current turn
 * 3. Proper ordering via turn_number instead of timestamps
 * 4. Scroll to bottom behavior - follows streaming text as it comes in
 * 5. Optional reversed order (newest first) for player history view
 * 6. Optional hiding of DM input contributions
 */
const TurnBasedNarrativeView = ({
  narrative,
  playerResponse,
  isNarrativeStreaming,
  isResponseStreaming,
  turns = [],
  onImageGenerated,
  campaignId,
  reversed = false,
  hideDMInput = false,
}) => {
  const containerRef = useRef(null);
  const [showScrollIndicator, setShowScrollIndicator] = useState(false);

  // Track streaming content length for auto-scroll trigger
  // This changes every time new streaming content arrives in any turn
  const streamingContentLength = useMemo(() => {
    return turns.reduce((total, turn) => {
      return total + (turn.streamingText?.length || 0);
    }, 0);
  }, [turns]);

  // Scroll handling
  const checkScrollPosition = useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setShowScrollIndicator(!isNearBottom);
  }, []);

  const scrollToBottom = useCallback((options = {}) => {
    const container = containerRef.current;
    if (!container) return;
    const behavior = options.behavior || 'smooth';

    // For reversed view, "bottom" is actually top (newest content)
    const targetScroll = reversed ? 0 : container.scrollHeight;

    if (typeof container.scrollTo === 'function') {
      container.scrollTo({ top: targetScroll, behavior });
    } else {
      container.scrollTop = targetScroll;
    }
  }, [reversed]);

  // Auto-scroll on new turns or streaming content changes
  useEffect(() => {
    requestAnimationFrame(() => {
      scrollToBottom({ behavior: 'smooth' });
      setTimeout(checkScrollPosition, 500);
    });
  }, [turns.length, streamingContentLength, narrative, playerResponse, checkScrollPosition, scrollToBottom]);

  // Scroll listener
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.addEventListener('scroll', checkScrollPosition);
    checkScrollPosition();
    return () => container.removeEventListener('scroll', checkScrollPosition);
  }, [checkScrollPosition]);

  const handleScrollIndicatorClick = () => {
    scrollToBottom({ behavior: 'smooth' });
  };

  // Check if we have streaming content that isn't already in a turn
  const streamingText = narrative || playerResponse || '';
  const isActivelyStreaming = isNarrativeStreaming || isResponseStreaming;

  // Find if the latest turn already has this streaming content
  const latestTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const latestTurnHasStreaming = latestTurn?.isStreaming || (latestTurn?.streamingText?.length > 0);

  // Only show separate streaming if we have content AND it's not already in a turn
  const showStreamingInLatestTurn = streamingText && !latestTurnHasStreaming;

  // Order turns based on reversed prop
  const orderedTurns = useMemo(() => {
    if (reversed) {
      return [...turns].reverse();
    }
    return turns;
  }, [turns, reversed]);

  return (
    <div className={`streaming-narrative-container ${reversed ? 'reversed' : ''}`} ref={containerRef}>
      {/* Turn-Based Message History */}
      {turns.length > 0 || showStreamingInLatestTurn ? (
        <div className="message-history turn-based">
          {orderedTurns.map((turn, index) => {
            // In reversed mode, the "latest" turn is at index 0
            // In normal mode, the "latest" turn is at the end
            const isLatestTurn = reversed
              ? index === 0
              : index === orderedTurns.length - 1;

            // Inject streaming content into the latest turn if it doesn't have its own
            const turnWithStreaming = isLatestTurn && showStreamingInLatestTurn
              ? {
                  ...turn,
                  streamingText: turn.streamingText || streamingText,
                  isStreaming: turn.isStreaming || isActivelyStreaming,
                }
              : turn;

            return (
              <TurnMessage
                key={turn.turn_number}
                turn={turnWithStreaming}
                campaignId={campaignId}
                onImageGenerated={onImageGenerated}
                hideDMInput={hideDMInput}
              />
            );
          })}

          {/* If no turns but streaming, show as a standalone streaming turn */}
          {turns.length === 0 && showStreamingInLatestTurn && (
            <TurnMessage
              key="streaming-turn"
              turn={{
                turn_number: 0,
                input: null,
                streamingText: streamingText,
                finalMessage: null,
                isStreaming: isActivelyStreaming,
                error: null,
              }}
              campaignId={campaignId}
              onImageGenerated={onImageGenerated}
              hideDMInput={hideDMInput}
            />
          )}
        </div>
      ) : (
        <div className="empty-state">
          <p style={{ color: '#666', textAlign: 'center', padding: '40px' }}>
            No messages yet. Start the conversation to see turns here.
          </p>
        </div>
      )}

      {/* Scroll to bottom indicator */}
      {showScrollIndicator && turns.length > 0 && (
        <button
          className="scroll-to-bottom-indicator"
          onClick={handleScrollIndicatorClick}
          aria-label="Scroll to bottom"
          title="More content below"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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

export default TurnBasedNarrativeView;
