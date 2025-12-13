import React, { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../config/api.js';

/**
 * SceneImageTrio - Displays three scene images as a triptych
 *
 * A decorative framed display showing location, background, and moment images
 * side by side. Can receive data directly or fetch by setId.
 *
 * @param {Object} props
 * @param {Object} [props.imageSet] - Pre-fetched image set data
 * @param {string} [props.setId] - Set ID to fetch data (used if imageSet not provided)
 * @param {boolean} [props.showLabels=true] - Show image type labels
 * @param {boolean} [props.showDescriptions=false] - Show descriptions on hover
 * @param {Function} [props.onImageClick] - Callback when image is clicked (receives image object)
 * @param {string} [props.size='medium'] - Size variant: 'small', 'medium', 'large'
 * @param {string} [props.className] - Additional CSS classes
 */
const SceneImageTrio = ({
  imageSet: providedImageSet,
  setId,
  showLabels = true,
  showDescriptions = false,
  onImageClick,
  size = 'medium',
  className = ''
}) => {
  const [imageSet, setImageSet] = useState(providedImageSet);
  const [isLoading, setIsLoading] = useState(false);
  const [hoveredImage, setHoveredImage] = useState(null);

  // Fetch image set if setId provided and no imageSet
  const fetchImageSet = useCallback(async () => {
    if (!setId) return;

    setIsLoading(true);
    try {
      const response = await fetch(
        `${API_CONFIG.BACKEND_URL}/api/scene-images/${setId}`,
        { headers: { 'Content-Type': 'application/json' } }
      );

      if (response.ok) {
        const data = await response.json();
        setImageSet(data);
      }
    } catch (error) {
      console.error('Error fetching scene image set:', error);
    } finally {
      setIsLoading(false);
    }
  }, [setId]);

  useEffect(() => {
    if (providedImageSet) {
      setImageSet(providedImageSet);
    } else if (setId) {
      fetchImageSet();
    }
  }, [providedImageSet, setId, fetchImageSet]);

  // Size configurations
  const sizeConfig = {
    small: { height: '120px', labelSize: '10px' },
    medium: { height: '180px', labelSize: '11px' },
    large: { height: '240px', labelSize: '12px' }
  };

  const config = sizeConfig[size] || sizeConfig.medium;

  const typeLabels = {
    location_ambiance: 'Location',
    background_detail: 'Background',
    moment_focus: 'Moment',
  };

  const typeOrder = ['location_ambiance', 'background_detail', 'moment_focus'];

  // Sort images by type order
  const sortedImages = imageSet?.images
    ? [...imageSet.images].sort(
        (a, b) => typeOrder.indexOf(a.type) - typeOrder.indexOf(b.type)
      )
    : [];

  const handleImageClick = (image) => {
    if (onImageClick && image.status === 'complete' && image.image_url) {
      onImageClick(image);
    }
  };

  const renderImage = (image, index) => {
    const isComplete = image.status === 'complete';
    const isFailed = image.status === 'failed';
    const isGenerating = image.status === 'generating' || image.status === 'pending';
    const isHovered = hoveredImage === image.type;
    const isMiddle = index === 1;

    return (
      <div
        key={image.type}
        className={`trio-panel ${isMiddle ? 'center' : ''} ${isComplete ? 'complete' : ''}`}
        style={{ height: config.height }}
        onClick={() => handleImageClick(image)}
        onMouseEnter={() => setHoveredImage(image.type)}
        onMouseLeave={() => setHoveredImage(null)}
      >
        {/* Image content */}
        <div className="panel-content">
          {isGenerating && (
            <div className="panel-generating">
              <div className="pulse-ring" />
              <div className="spinner" />
            </div>
          )}

          {isFailed && (
            <div className="panel-failed">
              <span className="failed-icon">⚠</span>
              <span className="failed-text">Failed</span>
            </div>
          )}

          {isComplete && image.image_url && (
            <img
              src={`${API_CONFIG.BACKEND_URL}${image.image_url}`}
              alt={image.description || typeLabels[image.type]}
              loading="lazy"
            />
          )}

          {/* Hover overlay with description */}
          {showDescriptions && isComplete && isHovered && image.description && (
            <div className="description-overlay">
              <p>{image.description}</p>
            </div>
          )}
        </div>

        {/* Label */}
        {showLabels && (
          <div className="panel-label" style={{ fontSize: config.labelSize }}>
            {typeLabels[image.type] || image.type}
          </div>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className={`scene-image-trio loading ${className}`}>
        <div className="trio-loading">
          <div className="spinner" />
          <span>Loading images...</span>
        </div>
      </div>
    );
  }

  if (!imageSet || sortedImages.length === 0) {
    return null;
  }

  return (
    <div className={`scene-image-trio ${size} ${className}`}>
      {/* Decorative frame */}
      <div className="trio-frame">
        {/* Corner decorations */}
        <div className="frame-corner top-left" />
        <div className="frame-corner top-right" />
        <div className="frame-corner bottom-left" />
        <div className="frame-corner bottom-right" />

        {/* Image panels */}
        <div className="trio-panels">
          {sortedImages.map((image, index) => renderImage(image, index))}
        </div>

        {/* Decorative dividers between panels */}
        <div className="panel-divider left" />
        <div className="panel-divider right" />
      </div>

      <style>{`
        .scene-image-trio {
          --trio-bg: #1a1a2e;
          --trio-border: #3d3d5c;
          --trio-accent: #6366f1;
          --trio-gold: #d4a574;
          --trio-text: #e0e0e0;
          --trio-text-muted: #888;
        }

        .scene-image-trio.loading {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 180px;
        }

        .scene-image-trio .trio-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          color: var(--trio-text-muted);
        }

        .scene-image-trio .trio-frame {
          position: relative;
          background: linear-gradient(145deg, #252540 0%, var(--trio-bg) 100%);
          border: 3px solid var(--trio-border);
          border-radius: 12px;
          padding: 12px;
          box-shadow:
            0 4px 20px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        }

        /* Decorative corner flourishes */
        .scene-image-trio .frame-corner {
          position: absolute;
          width: 20px;
          height: 20px;
          border-color: var(--trio-gold);
          border-style: solid;
          border-width: 0;
          opacity: 0.6;
        }

        .scene-image-trio .frame-corner.top-left {
          top: 4px;
          left: 4px;
          border-top-width: 2px;
          border-left-width: 2px;
          border-top-left-radius: 6px;
        }

        .scene-image-trio .frame-corner.top-right {
          top: 4px;
          right: 4px;
          border-top-width: 2px;
          border-right-width: 2px;
          border-top-right-radius: 6px;
        }

        .scene-image-trio .frame-corner.bottom-left {
          bottom: 4px;
          left: 4px;
          border-bottom-width: 2px;
          border-left-width: 2px;
          border-bottom-left-radius: 6px;
        }

        .scene-image-trio .frame-corner.bottom-right {
          bottom: 4px;
          right: 4px;
          border-bottom-width: 2px;
          border-right-width: 2px;
          border-bottom-right-radius: 6px;
        }

        .scene-image-trio .trio-panels {
          display: flex;
          gap: 8px;
          position: relative;
        }

        .scene-image-trio .trio-panel {
          flex: 1;
          display: flex;
          flex-direction: column;
          border-radius: 6px;
          overflow: hidden;
          background: #0f0f1a;
          border: 1px solid var(--trio-border);
          transition: all 0.3s ease;
          cursor: pointer;
        }

        .scene-image-trio .trio-panel:hover {
          border-color: var(--trio-accent);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(99, 102, 241, 0.2);
        }

        .scene-image-trio .trio-panel.center {
          flex: 1.2;
        }

        .scene-image-trio .trio-panel.complete {
          border-color: rgba(34, 197, 94, 0.4);
        }

        .scene-image-trio .panel-content {
          flex: 1;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .scene-image-trio .panel-content img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          transition: transform 0.3s ease;
        }

        .scene-image-trio .trio-panel:hover .panel-content img {
          transform: scale(1.05);
        }

        .scene-image-trio .panel-generating {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          position: relative;
        }

        .scene-image-trio .pulse-ring {
          position: absolute;
          width: 50px;
          height: 50px;
          border: 2px solid var(--trio-accent);
          border-radius: 50%;
          animation: pulse-ring 1.5s ease-out infinite;
          opacity: 0;
        }

        @keyframes pulse-ring {
          0% {
            transform: scale(0.5);
            opacity: 0.8;
          }
          100% {
            transform: scale(1.5);
            opacity: 0;
          }
        }

        .scene-image-trio .spinner {
          width: 24px;
          height: 24px;
          border: 2px solid var(--trio-border);
          border-top-color: var(--trio-accent);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .scene-image-trio .panel-failed {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          color: #ef4444;
        }

        .scene-image-trio .failed-icon {
          font-size: 24px;
        }

        .scene-image-trio .failed-text {
          font-size: 10px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .scene-image-trio .description-overlay {
          position: absolute;
          inset: 0;
          background: rgba(0, 0, 0, 0.85);
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 12px;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .scene-image-trio .description-overlay p {
          margin: 0;
          font-size: 11px;
          line-height: 1.4;
          color: var(--trio-text);
          text-align: center;
          max-height: 100%;
          overflow: auto;
        }

        .scene-image-trio .panel-label {
          padding: 6px 8px;
          text-align: center;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          font-weight: 600;
          color: var(--trio-text-muted);
          background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
          border-top: 1px solid rgba(255,255,255,0.05);
        }

        /* Decorative dividers */
        .scene-image-trio .panel-divider {
          display: none; /* Hidden for now, can be enabled for extra decoration */
        }

        /* Size variants */
        .scene-image-trio.small .trio-frame {
          padding: 8px;
        }

        .scene-image-trio.small .trio-panels {
          gap: 6px;
        }

        .scene-image-trio.large .trio-frame {
          padding: 16px;
          border-width: 4px;
        }

        .scene-image-trio.large .frame-corner {
          width: 28px;
          height: 28px;
          border-width: 3px;
        }

        /* Responsive */
        @media (max-width: 640px) {
          .scene-image-trio .trio-panels {
            flex-direction: column;
          }

          .scene-image-trio .trio-panel.center {
            flex: 1;
          }
        }
      `}</style>
    </div>
  );
};

export default SceneImageTrio;
