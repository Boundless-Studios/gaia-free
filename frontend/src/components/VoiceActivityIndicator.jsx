import { useEffect, useState } from 'react';
import apiService from '../services/apiService';
import './VoiceActivityIndicator.css';

const VoiceActivityIndicator = ({ sessionId, isRecording }) => {
  const [voiceActive, setVoiceActive] = useState(false);
  
  useEffect(() => {
    if (!isRecording || !sessionId) {
      setVoiceActive(false);
      return;
    }
    
    // Poll for voice activity status
    const pollVoiceActivity = async () => {
      try {
        const data = await apiService.getVoiceActivity(sessionId);
        if (data) {
          setVoiceActive(data.voice_active);
        }
      } catch (error) {
        console.error('Failed to poll voice activity:', error);
      }
    };
    
    // Poll every 200ms
    const interval = setInterval(pollVoiceActivity, 200);
    
    return () => clearInterval(interval);
  }, [sessionId, isRecording]);
  
  return (
    <div className={`voice-activity-indicator ${voiceActive ? 'active' : ''}`}>
      <div className="indicator-dot" />
      <span className="indicator-label">Voice</span>
    </div>
  );
};

export default VoiceActivityIndicator;