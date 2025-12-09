import React from 'react';
import PropTypes from 'prop-types';
import { useAudioStream } from '../../context/audioStreamContext.jsx';
import './AudioPlayerBar.css';

const formatClockTime = (isoString) => {
  if (!isoString) {
    return '';
  }
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (error) {
    console.warn('Failed to format audio timestamp', error);
    return '';
  }
};

const formatDuration = (seconds) => {
  if (!seconds || Number.isNaN(seconds)) {
    return '';
  }
  const wholeSeconds = Math.floor(seconds);
  const mins = Math.floor(wholeSeconds / 60).toString().padStart(2, '0');
  const secs = (wholeSeconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

const AudioPlayerBar = ({
  sessionId = 'default',
  queueInfo = null,
  userAudioBlocked = false,
  onUnlockUserAudio = null,
}) => {
  const {
    currentSessionId: liveSessionId,
    isStreaming,
    needsUserGesture: streamNeedsGesture,
    lastError: streamError,
    resumePlayback,
    isMuted: streamMuted,
    toggleMute: toggleStreamMute,
    pendingChunkCount,
  } = useAudioStream();

  // Combine both audio blocked states
  const audioNeedsUnlock = streamNeedsGesture || userAudioBlocked;

  // Only show audio player bar if streaming, needs gesture, or user audio is blocked
  if (!isStreaming && !audioNeedsUnlock && !streamError && pendingChunkCount === 0) {
    return null;
  }

  // Handle unlock - try both unlock methods IN PARALLEL
  // iOS Safari requires the user gesture to be "active" when play() is called,
  // so we run both unlocks simultaneously to stay within the gesture context
  const handleUnlockAudio = async () => {
    const unlockPromises = [];

    // Unlock user audio queue first (plays silent audio to prime browser)
    if (userAudioBlocked && onUnlockUserAudio) {
      unlockPromises.push(onUnlockUserAudio());
    }

    // Resume stream playback
    if (streamNeedsGesture) {
      unlockPromises.push(resumePlayback());
    }

    // Run all unlocks in parallel within the same gesture context
    if (unlockPromises.length > 0) {
      await Promise.all(unlockPromises);
    }
  };

  const backendPendingRequests = queueInfo?.pendingRequests ?? [];
  const backendPendingChunks = backendPendingRequests.reduce(
    (sum, request) => sum + (request.chunk_count || 0),
    0,
  );
  const backendPendingRequestsCount = backendPendingRequests.length;
  const backendCurrentRequest = queueInfo?.currentRequest;

  const streamQueueSuffix =
    pendingChunkCount > 0
      ? ` · ${pendingChunkCount} clip${pendingChunkCount === 1 ? '' : 's'} queued`
      : '';

  const backendQueueSuffix =
    backendPendingChunks > 0
      ? `${backendPendingChunks} chunk${backendPendingChunks === 1 ? '' : 's'} pending`
      : 'No pending chunks';

  const renderLiveStatus = () => (
    <div className="audio-player-bar__live">
      <div className="audio-player-bar__live-meta">
        <span
          className={`audio-player-bar__status-dot ${
            isStreaming ? 'audio-player-bar__status-dot--live'
            : audioNeedsUnlock ? 'audio-player-bar__status-dot--warn'
            : 'audio-player-bar__status-dot--idle'
          }`}
        />
        <div>
          <div className="audio-player-bar__live-title">Live Audio</div>
          <div className="audio-player-bar__live-desc">
            {isStreaming
              ? `Listening to ${liveSessionId || 'active campaign'}${streamQueueSuffix}`
              : audioNeedsUnlock
                ? `Tap to enable audio${streamQueueSuffix}`
                : streamError
                  ? streamError
                  : `Waiting for narration${streamQueueSuffix}`}
          </div>
          {queueInfo && (
            <div className="audio-player-bar__queue-desc">
              {backendCurrentRequest && (
                <span>
                  Current request:{' '}
                  {backendCurrentRequest.played_count ?? 0}/{backendCurrentRequest.chunk_count ?? 0} chunks played
                </span>
              )}
              <span>
                {backendQueueSuffix}
                {backendPendingRequestsCount > 0
                  ? ` · ${backendPendingRequestsCount} queued request${backendPendingRequestsCount === 1 ? '' : 's'}`
                  : ''}
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="audio-player-bar__live-actions">
        {audioNeedsUnlock && (
          <button
            type="button"
            className="audio-player-bar__button audio-player-bar__button--primary"
            onClick={handleUnlockAudio}
          >
            Enable Audio
          </button>
        )}
        {(isStreaming || audioNeedsUnlock) && (
          <button
            type="button"
            className={`audio-player-bar__button ${streamMuted ? 'audio-player-bar__button--muted' : ''}`}
            onClick={toggleStreamMute}
          >
            {streamMuted ? 'Unmute' : 'Mute'}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <section className="audio-player-bar" aria-label="Narration audio controls">
      {renderLiveStatus()}
    </section>
  );
};

AudioPlayerBar.propTypes = {
  sessionId: PropTypes.string,
  queueInfo: PropTypes.shape({
    pendingCount: PropTypes.number,
    currentRequest: PropTypes.shape({
      request_id: PropTypes.string,
      chunk_count: PropTypes.number,
      played_count: PropTypes.number,
    }),
    pendingRequests: PropTypes.arrayOf(
      PropTypes.shape({
        request_id: PropTypes.string,
        chunk_count: PropTypes.number,
      }),
    ),
    timestamp: PropTypes.string,
  }),
  userAudioBlocked: PropTypes.bool,
  onUnlockUserAudio: PropTypes.func,
};

export default AudioPlayerBar;
