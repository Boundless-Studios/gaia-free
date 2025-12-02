import React from 'react';
import NestedNarrativeView from './NestedNarrativeView';
import { narrativeStyles, sharedStyles } from '../lib/sharedStyles';
import { cn } from '../lib/tailwindComponents';
import apiService from '../services/apiService';
import '../styles/custom-scrollbars.css';
import './ChatMessage.css';

const NarrativeView = ({ narrative, className = '', sessionId = null }) => {
  // Audio now handled by synchronized streaming via WebSocket
  const [isPlaying, setIsPlaying] = React.useState(false);

  if (!narrative) return null;

  let processedNarrative = narrative;
  
  // If narrative is a string that looks like JSON, try to parse it
  if (typeof narrative === 'string' && narrative.trim().startsWith('{')) {
    try {
      processedNarrative = JSON.parse(narrative);
    } catch {
      // If parsing fails, keep it as a string
      processedNarrative = narrative;
    }
  }

  // Function to extract text from narrative (handles both string and object formats)
  const getNarrativeText = () => {
    if (typeof processedNarrative === 'string') {
      return processedNarrative;
    } else if (typeof processedNarrative === 'object' && processedNarrative !== null) {
      // Extract text from nested object structure
      const extractText = (obj) => {
        if (typeof obj === 'string') return obj;
        if (Array.isArray(obj)) return obj.map(extractText).join(' ');
        if (typeof obj === 'object' && obj !== null) {
          return Object.values(obj).map(extractText).join(' ');
        }
        return '';
      };
      return extractText(processedNarrative);
    }
    return '';
  };

  // Handle play/stop button click
  const sessionForRequest = sessionId === 'default' ? 'default-session' : (sessionId || 'default-session');

  const handlePlayStop = async () => {
    if (isPlaying) {
      try {
        await apiService.stopTTSQueue(sessionForRequest);
        setIsPlaying(false);
      } catch (error) {
        console.warn('Failed to stop TTS queue:', error);
      }
    } else {
      try {
        const textToSpeak = getNarrativeText();
        await apiService.synthesizeTTS(
          {
            text: textToSpeak,
            voice: 'nathaniel',
            speed: 1.0,
          },
          sessionForRequest,
        );
        setIsPlaying(true);
        console.log('TTS triggered - backend will handle synchronized streaming');
      } catch (error) {
        console.error('Error playing narrative:', error);
      }
    }
  };

  // If narrative is an object (or was parsed from JSON), use the nested view
  if (typeof processedNarrative === 'object' && processedNarrative !== null) {
    return (
      <div className={cn(
        sharedStyles.baseView,
        narrativeStyles.view,
        narrativeStyles.mobile.view,
        className
      )}>
        <div className={cn(
          sharedStyles.baseHeader,
          narrativeStyles.header,
          narrativeStyles.mobile.header
        )}>
          <div className={sharedStyles.baseIcon}>📖</div>
          <h2 className={cn(
            sharedStyles.baseTitle,
            narrativeStyles.title,
            narrativeStyles.mobile.title
          )}>Narrative</h2>
          <button 
            className={cn(
              narrativeStyles.playButton,
              isPlaying && narrativeStyles.playButtonPlaying
            )}
            onClick={handlePlayStop}
            title={isPlaying ? 'Stop narration' : 'Play narration'}
          >
            {isPlaying ? '⏹️' : '▶️'}
          </button>
        </div>
        <div className={cn(
          narrativeStyles.content,
          narrativeStyles.scrollbar,
          narrativeStyles.mobile.content,
          narrativeStyles.selection
        )}>
          <NestedNarrativeView narrative={processedNarrative} />
        </div>
      </div>
    );
  }

  // If narrative is a string, use the original view
  return (
    <div className={cn(
      sharedStyles.baseView,
      narrativeStyles.view,
      narrativeStyles.mobile.view,
      className
    )}>
      <div className={cn(
        sharedStyles.baseHeader,
        narrativeStyles.header,
        narrativeStyles.mobile.header
      )}>
        <div className={sharedStyles.baseIcon}>📖</div>
        <h2 className={cn(
          sharedStyles.baseTitle,
          narrativeStyles.title,
          narrativeStyles.mobile.title
        )}>Narrative</h2>
        <button 
          className={cn(
            narrativeStyles.playButton,
            isPlaying && narrativeStyles.playButtonPlaying
          )}
          onClick={handlePlayStop}
          title={isPlaying ? 'Stop narration' : 'Play narration'}
        >
          {isPlaying ? '⏹️' : '▶️'}
        </button>
      </div>
      <div className={cn(
        narrativeStyles.content,
        narrativeStyles.scrollbar,
        narrativeStyles.mobile.content,
        narrativeStyles.selection
      )}>
        <div className={cn(
          narrativeStyles.text,
          narrativeStyles.mobile.text
        )}>
          {processedNarrative.split('\n')
            .filter(paragraph => paragraph.trim()) // Filter out empty lines
            .map((paragraph, index) => (
              <div key={index} className="chat-message-container user">
                <div className="chat-message-content">
                  {paragraph}
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
};

export default NarrativeView;
