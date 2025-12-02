import { useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '../config/api.js';
import { Button } from './base-ui/Button';
import './ImagePopup.css';

const ImagePopup = ({ imageUrl, imagePath, imagePrompt, duration = 5000, onClose }) => {
  const [isVisible, setIsVisible] = useState(false);
  const closeTimeoutRef = useRef(null);
  const imageSrc = imageUrl || (imagePath ? `${API_CONFIG.BACKEND_URL}/api/images/${imagePath.split('/').pop()}` : null);

  useEffect(() => {
    let visibilityTimeout;
    let autoCloseTimeout;

    if (imageSrc) {
      // Small delay to trigger animation
      visibilityTimeout = setTimeout(() => setIsVisible(true), 100);

      // Auto-close after duration
      autoCloseTimeout = setTimeout(() => {
        setIsVisible(false);
        closeTimeoutRef.current = setTimeout(() => {
          if (typeof onClose === 'function') {
            onClose('auto');
          }
        }, 300); // Wait for fade-out animation
      }, duration);

      return () => {
        clearTimeout(visibilityTimeout);
        clearTimeout(autoCloseTimeout);
        if (closeTimeoutRef.current) {
          clearTimeout(closeTimeoutRef.current);
        }
      };
    }
  }, [imageSrc, duration, onClose]);

  const handleClose = () => {
    setIsVisible(false);
    if (closeTimeoutRef.current) {
      clearTimeout(closeTimeoutRef.current);
    }
    if (typeof onClose === 'function') {
      closeTimeoutRef.current = setTimeout(() => onClose('manual'), 300);
    }
  };

  // Handle ESC key to close popup
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        handleClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleClose]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (closeTimeoutRef.current) {
        clearTimeout(closeTimeoutRef.current);
      }
    };
  }, []);

  if (!imageSrc) return null;

  const handleClick = (e) => {
    // Only close on direct click, not on keyboard events
    e.stopPropagation();
    handleClose();
  };

  const handleOverlayClick = (e) => {
    // Only respond to mouse clicks on the overlay itself, not keyboard events
    // This allows global keyboard shortcuts to work through the overlay
    if (e.target === e.currentTarget) {
      handleClick(e);
    }
  };

  return (
    <div
      className={`image-popup-overlay ${isVisible ? 'visible' : ''}`}
      onClick={handleOverlayClick}
      onKeyDown={(e) => e.stopPropagation()}
    >
      <div className="image-popup-container" onClick={(e) => e.stopPropagation()}>
        <Button className="image-popup-close" onClick={handleClick} variant="ghost">×</Button>
        <img
          src={imageSrc}
          alt={imagePrompt || "D&D Scene"}
          className="image-popup-image"
        />
        {imagePrompt && (
          <div className="image-popup-caption">
            {imagePrompt}
          </div>
        )}
      </div>
    </div>
  );
};

export default ImagePopup;
