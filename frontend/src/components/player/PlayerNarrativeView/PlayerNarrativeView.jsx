import { useEffect, useRef, useState } from 'react';
import SceneImageDisplay from './SceneImageDisplay.jsx';
import apiService from '../../../services/apiService.js';
import './PlayerNarrativeView.css';

const PlayerNarrativeView = ({
  structuredData,
  campaignId,
  campaignMessages = [],
  isLoading,
  streamingNarrative = '',
  streamingResponse = '',
  isNarrativeStreaming = false,
  isResponseStreaming = false
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [images, setImages] = useState([]);
  const narrativeHistoryRef = useRef(null);

  // Auto-scroll to latest message in narrative history
  useEffect(() => {
    if (narrativeHistoryRef.current && structuredData?.all_narratives?.length > 0) {
      narrativeHistoryRef.current.scrollTop = narrativeHistoryRef.current.scrollHeight;
    }
  }, [structuredData?.all_narratives]);

  // Fetch campaign images
  useEffect(() => {
    if (campaignId) {
      const fetchImages = async () => {
        try {
          const imageData = await apiService.fetchRecentImages(5, campaignId);
          setImages(imageData || []);
        } catch (error) {
          console.error('Failed to fetch campaign images:', error);
        }
      };

      fetchImages();
      // Poll for new images every 5 seconds
      const interval = setInterval(fetchImages, 15000);
      return () => clearInterval(interval);
    }
  }, [campaignId]);

  // Get the latest scene image
  const latestImage = images.length > 0 ? images[0] : null;

  if (!structuredData) {
    return (
      <div className="player-narrative-view" data-testid="player-narrative">
        <div className="narrative-placeholder">
          <div className="placeholder-icon">📖</div>
          <h3>Waiting for Story</h3>
          <p>The adventure will begin when the DM starts the narrative...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="player-narrative-view" data-testid="player-narrative">
      {/* Scene Image Display */}
      <div className="narrative-scene-container">
        <SceneImageDisplay
          image={latestImage}
          campaignId={campaignId}
          onClick={() => setIsModalOpen(true)}
        />

        {/* Narrative Text Overlay */}
        <div className="narrative-overlay">
          <div className="narrative-content">
            <div className="narrative-header">
              <h2 className="narrative-title">
                <span className="narrative-icon">📖</span>
                Story
              </h2>
            </div>

            {/* Narrative Text */}
            <div className="narrative-text">
              {structuredData.all_narratives && structuredData.all_narratives.length > 0 ? (
                <div className="narrative-history" ref={narrativeHistoryRef}>
                  {structuredData.all_narratives.map((narrative, index) => (
                    <div key={narrative.id || index} className="narrative-entry">
                      <p className="narrative-paragraph">
                        {narrative.content}
                      </p>
                      {narrative.speaker && (
                        <div className="narrative-speaker">
                          — {narrative.speaker}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="story-content">
                  {/* Show last player message immediately after submission */}
                  {campaignMessages.length > 0 &&
                   campaignMessages[campaignMessages.length - 1].sender === 'user' && (
                    <div className="player-message-section">
                      <div className="player-message-label">
                        👤 You:
                      </div>
                      <p className="player-message-text">
                        {campaignMessages[campaignMessages.length - 1].text}
                      </p>
                    </div>
                  )}

                  {/* Show streaming content if it exists, otherwise show final answer */}
                  {(streamingNarrative || streamingResponse) ? (
                    <div className="answer-section streaming">
                      <div className="answer-label">
                        💬 {isNarrativeStreaming ? 'Scene Description' : 'Answer'}:
                        {structuredData.turn_info && (
                          <span className="turn-info">
                            Turn {structuredData.turn_info.turn_number}
                          </span>
                        )}
                      </div>
                      <p className="answer-text">
                        {streamingNarrative || streamingResponse}
                        {(isNarrativeStreaming || isResponseStreaming) && <span className="streaming-cursor">▮</span>}
                      </p>
                    </div>
                  ) : (
                    /* Answer Section - shown only when streaming content is cleared */
                    structuredData.answer && (
                      <div className="answer-section">
                        <div className="answer-label">
                          💬 Answer:
                          {structuredData.turn_info && (
                            <span className="turn-info">
                              Turn {structuredData.turn_info.turn_number}
                            </span>
                          )}
                        </div>
                        <p className="answer-text">
                          {structuredData.answer}
                        </p>
                      </div>
                    )
                  )}
                </div>
              )}
            </div>

          </div>

          {/* Environmental Information - safely handle complex data */}
          {structuredData.environmental_conditions && (
            <div className="narrative-environmental">
              <span className="environmental-icon">🌍</span>
              <span className="environmental-text">
                {typeof structuredData.environmental_conditions === 'string'
                  ? structuredData.environmental_conditions
                  : JSON.stringify(structuredData.environmental_conditions)}
              </span>
            </div>
          )}

        </div>

        {/* Loading overlay */}
        {isLoading && (
          <div className="narrative-loading">
            <div className="loading-spinner">⚡</div>
            <span>The story unfolds...</span>
          </div>
        )}
      </div>

      {/* Full-screen Modal */}
      {isModalOpen && (
        <div
          className="narrative-modal"
          onClick={() => setIsModalOpen(false)}
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              onClick={() => setIsModalOpen(false)}
            >
              ✕
            </button>

            {latestImage && (
              <img
                src={latestImage.imageUrl || `${apiService.baseUrl}${latestImage.path}`}
                alt={latestImage.imagePrompt || 'Scene image'}
                className="modal-image"
              />
            )}

          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerNarrativeView;
