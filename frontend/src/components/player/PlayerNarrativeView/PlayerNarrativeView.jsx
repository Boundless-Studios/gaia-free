import { useEffect, useState } from 'react';
import SceneImageDisplay from './SceneImageDisplay.jsx';
import apiService from '../../../services/apiService.js';
import './PlayerNarrativeView.css';

const PlayerNarrativeView = ({
  structuredData,
  campaignId,
  isLoading,
}) => {
  const [currentImageIndex, setCurrentImageIndex] = useState(0);
  const [images, setImages] = useState([]);

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

  // Get current image based on index
  const currentImage = images.length > 0 ? images[currentImageIndex] : null;

  // Reset to first image when images change
  useEffect(() => {
    if (images.length > 0 && currentImageIndex >= images.length) {
      setCurrentImageIndex(0);
    }
  }, [images.length, currentImageIndex]);

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
      {/* Scene Image Display with inline navigation */}
      <div className="narrative-scene-container">
        <SceneImageDisplay
          image={currentImage}
          campaignId={campaignId}
        />

        {/* Arrow Navigation - only show if multiple images */}
        {images.length > 1 && (
          <>
            <button
              className="scene-nav-button scene-nav-prev"
              onClick={() => setCurrentImageIndex((prev) => (prev - 1 + images.length) % images.length)}
              disabled={currentImageIndex === 0}
              aria-label="Previous image"
            >
              ‹
            </button>
            <button
              className="scene-nav-button scene-nav-next"
              onClick={() => setCurrentImageIndex((prev) => (prev + 1) % images.length)}
              disabled={currentImageIndex === images.length - 1}
              aria-label="Next image"
            >
              ›
            </button>
            <div className="scene-image-counter">
              {currentImageIndex + 1} / {images.length}
            </div>
          </>
        )}

        {/* Loading overlay */}
        {isLoading && (
          <div className="narrative-loading">
            <div className="loading-spinner">⚡</div>
            <span>The story unfolds...</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default PlayerNarrativeView;
