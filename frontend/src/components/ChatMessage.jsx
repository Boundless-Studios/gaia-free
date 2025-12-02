import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import './ChatMessage.css';
import apiService from '../services/apiService';

const extractText = (value) => {
  if (value == null) {
    return '';
  }

  if (typeof value === 'string') {
    return value;
  }

  if (Array.isArray(value)) {
    return value.map(extractText).join(' ');
  }

  if (typeof value === 'object') {
    return Object.values(value).map(extractText).join(' ');
  }

  return String(value);
};

const ChatMessage = ({ message, className = '', sessionId }) => {
  // Audio now handled by synchronized streaming via WebSocket

  // Get sender display name
  const getSenderName = () => {
    switch (message.sender) {
      case 'user': return 'You';
      case 'dm': return 'DM';
      case 'assistant': return 'Assistant';
      case 'system': return 'System';
      default: return message.sender;
    }
  };

  // Check if message has structured content (narrative and/or answer)
  const hasStructuredContent = message.structuredContent &&
    (message.structuredContent.narrative || message.structuredContent.answer);

  const queueSessionId = sessionId || message.sessionId || 'default';

  const sessionForRequest = queueSessionId === 'default' ? 'default-session' : queueSessionId;
  const [isPlaybackActive, setIsPlaybackActive] = React.useState(false);

  const lastRequestedRef = useRef(null);

  useEffect(() => {
    if (!isPlaybackActive) {
      lastRequestedRef.current = null;
    }
  }, [isPlaybackActive]);

  const stopPlayback = useCallback(async () => {
    try {
      await apiService.stopTTSQueue(sessionForRequest);
      setIsPlaybackActive(false);
    } catch (error) {
      console.warn('Failed to stop TTS queue:', error);
    }
  }, [sessionForRequest]);

  const playText = useCallback(
    async (text) => {
      const trimmed = text?.trim();
      if (!trimmed) {
        return;
      }

      try {
        await apiService.synthesizeTTS(
          {
            text: trimmed,
            voice: 'nathaniel',
            speed: 1.0,
          },
          sessionForRequest,
        );
        setIsPlaybackActive(true);
        console.log('TTS triggered - backend will handle synchronized streaming');
      } catch (error) {
        console.error('Error playing message audio:', error);
      }
    },
    [sessionForRequest],
  );

  const handleQuickPlay = useCallback(
    async (text, key) => {
      const trimmed = text?.trim();
      if (!trimmed) {
        return;
      }

      const isSameRequest = lastRequestedRef.current === key && isPlaybackActive;
      if (isPlaybackActive) {
        await stopPlayback();
        if (isSameRequest) {
          lastRequestedRef.current = null;
          return;
        }
      }

      await playText(trimmed);
      lastRequestedRef.current = key;
    },
    [isPlaybackActive, stopPlayback, playText],
  );

  const narrativeText = useMemo(
    () => extractText(message.structuredContent?.narrative).trim(),
    [message.structuredContent?.narrative],
  );
  const answerText = useMemo(
    () => extractText(message.structuredContent?.answer).trim(),
    [message.structuredContent?.answer],
  );

  const hasNarrative = Boolean(narrativeText);
  const hasAnswer = Boolean(answerText);

  const isNarrativePlaying =
    isPlaybackActive && lastRequestedRef.current === 'narrative';
  const isAnswerPlaying =
    isPlaybackActive && lastRequestedRef.current === 'answer';

  return (
    <div className={`chat-message-container ${message.sender} ${className}`}>
      <div className="chat-message-header">
        <strong className="chat-message-sender">{getSenderName()}:</strong>
        {message.hasAudio && (
          <span className="chat-message-audio" aria-label="Audio available" title="Audio available">
            🔊
          </span>
        )}
      </div>

      <div className="chat-message-content">
        {hasStructuredContent ? (
          <>
            {/* Narrative Section */}
            {message.structuredContent.narrative && (
              <div className="message-narrative-section">
                <div className="message-section-header">
                  <div className="message-section-label">
                    📖 Narrative
                  </div>
                  {hasNarrative && (
                    <button
                      type="button"
                      className={`message-quick-play-button${isNarrativePlaying ? ' message-quick-play-button--active' : ''}`}
                      onClick={() => void handleQuickPlay(narrativeText, 'narrative')}
                      title={isNarrativePlaying ? 'Stop narration playback' : 'Play narration'}
                    >
                      {isNarrativePlaying ? '⏹️ Stop' : '▶️ Play'}
                    </button>
                  )}
                </div>
                <div className="message-section-content">
                  {message.structuredContent.narrative}
                </div>
              </div>
            )}

            {/* Answer Section */}
            {message.structuredContent.answer && (
              <div className="message-answer-section">
                <div className="message-section-header">
                  <div className="message-section-label">
                    💬 Answer
                  </div>
                  {hasAnswer && (
                    <button
                      type="button"
                      className={`message-quick-play-button${isAnswerPlaying ? ' message-quick-play-button--active' : ''}`}
                      onClick={() => void handleQuickPlay(answerText, 'answer')}
                      title={isAnswerPlaying ? 'Stop answer playback' : 'Play answer'}
                    >
                      {isAnswerPlaying ? '⏹️ Stop' : '▶️ Play'}
                    </button>
                  )}
                </div>
                <div className="message-section-content">
                  {message.structuredContent.answer}
                </div>
              </div>
            )}
          </>
        ) : (
          message.text
        )}
      </div>

      {message.timestamp && (
        <div className="chat-message-timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      )}
    </div>
  );
};

export default ChatMessage;
