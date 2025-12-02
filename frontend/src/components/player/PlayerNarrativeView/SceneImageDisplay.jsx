import React from 'react';
import { API_CONFIG } from '../../../config/api.js';

const SceneImageDisplay = ({ image, campaignId, onClick }) => {
  // Default placeholder scene
  const defaultScene = {
    imageUrl: null,
    imagePrompt: 'A mystical tavern filled with adventurers and the glow of magical artifacts',
    type: 'scene'
  };

  const currentImage = image || defaultScene;

  const handleImageClick = (e) => {
    e.preventDefault();
    if (onClick) {
      onClick();
    }
  };

  if (!currentImage.imageUrl && !currentImage.path) {
    // Show atmospheric placeholder
    return (
      <div className="scene-image-display scene-placeholder" onClick={handleImageClick}>
        <div className="placeholder-background">
          <div className="atmospheric-elements">
            <div className="element element-1">✨</div>
            <div className="element element-2">🏰</div>
            <div className="element element-3">🌙</div>
            <div className="element element-4">⚔️</div>
            <div className="element element-5">🐉</div>
          </div>
          <div className="placeholder-content">
            <h3 className="placeholder-title">No Scene Generated Yet</h3>
            <p className="placeholder-description">
              {currentImage.imagePrompt}
            </p>
          </div>
        </div>
      </div>
    );
  }

  const imageUrl = currentImage.imageUrl ||
                  (currentImage.path ? `${API_CONFIG.BACKEND_URL}${currentImage.path}` : null);

  return (
    <div className="scene-image-display" onClick={handleImageClick}>
      <img
        src={imageUrl}
        alt={currentImage.imagePrompt || 'Scene image'}
        className="scene-image"
        loading="lazy"
        onError={(e) => {
          console.error('Failed to load scene image:', e.target.src);
          e.target.style.display = 'none';
        }}
      />

      {/* Image overlay with title */}
      <div className="scene-overlay">
        <div className="scene-info">
          <span className="scene-type">{currentImage.type || 'scene'}</span>
          {currentImage.imagePrompt && (
            <span className="scene-prompt">{currentImage.imagePrompt}</span>
          )}
        </div>
      </div>

      {/* Click indicator */}
      <div className="click-indicator">
        <span className="click-icon">🔍</span>
        <span className="click-text">Click to expand</span>
      </div>
    </div>
  );
};

export default SceneImageDisplay;