import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useAudioStream } from '../../context/audioStreamContext.jsx';
import './AudioPlayerBar.css';

const AudioPlayerBar = ({
  userAudioBlocked = false,
  onUnlockUserAudio = null,
}) => {
  const {
    isStreaming,
    needsUserGesture: streamNeedsGesture,
    resumePlayback,
  } = useAudioStream();

  const [dismissed, setDismissed] = useState(false);

  // Combine both audio blocked states
  const audioNeedsUnlock = streamNeedsGesture || userAudioBlocked;

  // Auto-dismiss after 8 seconds if still showing
  useEffect(() => {
    if (!audioNeedsUnlock) {
      setDismissed(false); // Reset for next time
      return;
    }

    const timer = setTimeout(() => {
      setDismissed(true);
    }, 8000);

    return () => clearTimeout(timer);
  }, [audioNeedsUnlock]);

  // Don't show if not needed or dismissed
  if (!audioNeedsUnlock || dismissed) {
    return null;
  }

  // Handle unlock - run both in parallel within gesture context
  const handleUnlockAudio = () => {
    if (userAudioBlocked && onUnlockUserAudio) {
      onUnlockUserAudio();
    }
    if (streamNeedsGesture) {
      resumePlayback();
    }
    setDismissed(true);
  };

  return (
    <div className="audio-toast" onClick={handleUnlockAudio}>
      <span className="audio-toast__icon">🔊</span>
      <span className="audio-toast__text">Tap to enable audio</span>
    </div>
  );
};

AudioPlayerBar.propTypes = {
  userAudioBlocked: PropTypes.bool,
  onUnlockUserAudio: PropTypes.func,
};

export default AudioPlayerBar;
