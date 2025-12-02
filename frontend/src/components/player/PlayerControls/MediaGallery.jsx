import React, { useState, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../../../config/api.js';
import apiService from '../../../services/apiService.js';

const MediaGallery = ({ campaignId, recentMedia = [], refreshTrigger }) => {
  const [media, setMedia] = useState([]);
  const [selectedMedia, setSelectedMedia] = useState(null);
  const [filter, setFilter] = useState('all');
  const [isLoading, setIsLoading] = useState(false);

  // Fetch media from API
  const fetchMedia = useCallback(async () => {
    if (!campaignId) return;

    try {
      setIsLoading(true);
      const data = await apiService.fetchRecentImages(20, campaignId);

      if (data && Array.isArray(data)) {
        console.log(`🖼️ Player Media: Fetched ${data.length} images`);

        // Transform to match PlayerControls format
        const transformedMedia = data
          .filter(img => img && img.filename)
          .map(img => ({
            id: img.filename,
            type: extractTypeFromFilename(img.path || img.filename),
            url: `${API_CONFIG.BACKEND_URL}${img.path || `/api/media/${encodeURIComponent(campaignId)}/images/${encodeURIComponent(img.filename)}`}`,
            path: img.path || `/api/media/${encodeURIComponent(campaignId)}/images/${encodeURIComponent(img.filename)}`,
            description: img.prompt || extractPromptFromFilename(img.filename),
            timestamp: new Date(img.timestamp || Date.now()),
            imagePrompt: img.prompt || extractPromptFromFilename(img.filename),
            size: img.size,
            model: img.model || 'unknown'
          }));

        setMedia(transformedMedia);
      }
    } catch (error) {
      console.error('Failed to fetch campaign media:', error);
    } finally {
      setIsLoading(false);
    }
  }, [campaignId]);

  // Extract meaningful prompt from filename
  const extractPromptFromFilename = (filename) => {
    let prompt = filename;

    // Handle various filename formats
    if (prompt.startsWith('gemini_image_')) {
      prompt = 'D&D Scene';
    } else if (prompt.includes('_')) {
      // Remove common prefixes and suffixes
      prompt = prompt
        .replace(/^(gemini_image_|flux_|parasail_|test_scroll_|\d+_)/, '')
        .replace(/\.(png|jpg|jpeg|webp)$/i, '')
        .replace(/_/g, ' ')
        .replace(/\d{10,}/g, '') // Remove timestamps
        .trim();
    }

    // If prompt is empty or just numbers, use generic name
    if (!prompt || /^\d+$/.test(prompt)) {
      prompt = 'D&D Scene';
    }

    // Capitalize first letter of each word
    prompt = prompt.split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');

    return prompt;
  };

  // Extract type from filename or use 'scene' as default
  const extractTypeFromFilename = (filename) => {
    const lowerFilename = filename.toLowerCase();
    if (lowerFilename.includes('character') || lowerFilename.includes('npc')) return 'character';
    if (lowerFilename.includes('item') || lowerFilename.includes('weapon') || lowerFilename.includes('armor')) return 'item';
    if (lowerFilename.includes('map') || lowerFilename.includes('region')) return 'map';
    if (lowerFilename.includes('creature') || lowerFilename.includes('monster') || lowerFilename.includes('beast')) return 'creature';
    return 'scene'; // Default
  };

  // Initial fetch and polling
  useEffect(() => {
    fetchMedia();

    // Poll for new images every 60 seconds (reduced from 15s to avoid excessive API calls)
    // User can manually refresh anytime with the refresh button
    const interval = setInterval(fetchMedia, 60000);
    return () => clearInterval(interval);
  }, [fetchMedia]);

  // Instant refresh when WebSocket image_generated event triggers
  useEffect(() => {
    if (refreshTrigger) {
      console.log('📸 MediaGallery: Instant refresh triggered by WebSocket event');
      fetchMedia();
    }
  }, [refreshTrigger, fetchMedia]);

  // Filter media by type
  const filteredMedia = filter === 'all'
    ? media
    : media.filter(item => item.type === filter);

  // Get unique media types for filter buttons
  const mediaTypes = ['all', ...new Set(media.map(item => item.type))];

  // Get display URL for media item
  const getMediaUrl = (item) => {
    return item.url || (item.path ? `${API_CONFIG.BACKEND_URL}${item.path}` : null);
  };

  // Handle media selection
  const handleMediaSelect = (item) => {
    setSelectedMedia(item);
  };

  // Close modal
  const closeModal = () => {
    setSelectedMedia(null);
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    const now = new Date();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));

    if (hours > 0) {
      return `${hours}h ago`;
    } else if (minutes > 0) {
      return `${minutes}m ago`;
    } else {
      return 'Just now';
    }
  };

  // Get type icon
  const getTypeIcon = (type) => {
    switch (type) {
      case 'scene': return '🏞️';
      case 'character': return '👤';
      case 'item': return '⚔️';
      case 'map': return '🗺️';
      case 'creature': return '🐉';
      default: return '🖼️';
    }
  };

  return (
    <div className="media-gallery">
      {/* Header with inline filters */}
      <div className="gallery-header">
        <h3 className="section-title">
          <span className="section-icon">🖼️</span>
          Media Gallery
        </h3>
        <div className="media-filters">
          {mediaTypes.map(type => (
            <button
              key={type}
              className={`filter-btn ${filter === type ? 'active' : ''}`}
              onClick={() => setFilter(type)}
            >
              {type === 'all' ? '📂' : getTypeIcon(type)} {type.charAt(0).toUpperCase() + type.slice(1)}
            </button>
          ))}
        </div>
        <button
          className="refresh-btn"
          onClick={fetchMedia}
          disabled={isLoading}
          title="Refresh media"
        >
          {isLoading ? '⏳' : '🔄'}
        </button>
      </div>

      {/* Media Grid */}
      <div className="media-grid">
        {isLoading && media.length === 0 ? (
          <div className="no-media">
            <div className="no-media-icon">⏳</div>
            <p>Loading campaign media...</p>
          </div>
        ) : filteredMedia.length === 0 && media.length > 0 ? (
          <div className="no-media">
            <div className="no-media-icon">🔍</div>
            <p>No {filter} images found</p>
            <p className="no-media-hint">Try a different filter or refresh</p>
          </div>
        ) : filteredMedia.length === 0 ? (
          <div className="no-media">
            <div className="no-media-icon">🖼️</div>
            <p>No media found</p>
            <p className="no-media-hint">Images will appear here as they're generated during the campaign</p>
          </div>
        ) : (
          filteredMedia.map(item => (
            <div
              key={item.id}
              className="media-item"
              onClick={() => handleMediaSelect(item)}
            >
              <div className="media-thumbnail">
                {getMediaUrl(item) ? (
                  <img
                    src={getMediaUrl(item)}
                    alt={item.description || 'Campaign media'}
                    className="thumbnail-image"
                    loading="lazy"
                    onError={(e) => {
                      e.target.style.display = 'none';
                      e.target.nextSibling.style.display = 'flex';
                    }}
                  />
                ) : null}
                <div className="thumbnail-placeholder" style={{ display: 'none' }}>
                  <span className="placeholder-icon">{getTypeIcon(item.type)}</span>
                  <span className="placeholder-text">Loading...</span>
                </div>

                <div className="media-overlay">
                  <span className="media-type">{getTypeIcon(item.type)} {item.type}</span>
                  <span className="media-time">{formatTimestamp(item.timestamp)}</span>
                </div>
              </div>

              <div className="media-info">
                <p className="media-description">{item.description}</p>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modal for selected media */}
      {selectedMedia && (
        <div className="media-modal" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <button className="modal-close" onClick={closeModal}>
              ✕
            </button>

            <div className="modal-image-container">
              {getMediaUrl(selectedMedia) && (
                <img
                  src={getMediaUrl(selectedMedia)}
                  alt={selectedMedia.description || 'Campaign media'}
                  className="modal-image"
                />
              )}
            </div>

            <div className="modal-info">
              <div className="modal-header">
                <span className="modal-type">
                  {getTypeIcon(selectedMedia.type)} {selectedMedia.type.charAt(0).toUpperCase() + selectedMedia.type.slice(1)}
                </span>
                <span className="modal-timestamp">
                  {formatTimestamp(selectedMedia.timestamp)}
                </span>
              </div>

              <h3 className="modal-title">{selectedMedia.description}</h3>

              {selectedMedia.imagePrompt && (
                <div className="modal-prompt">
                  <p><strong>Generated from:</strong> {selectedMedia.imagePrompt}</p>
                </div>
              )}

              {(selectedMedia.size || selectedMedia.model) && (
                <div className="modal-details">
                  {selectedMedia.size && (
                    <p><strong>Size:</strong> {(selectedMedia.size / 1024).toFixed(1)} KB</p>
                  )}
                  {selectedMedia.model && selectedMedia.model !== 'unknown' && (
                    <p><strong>Model:</strong> {selectedMedia.model}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MediaGallery;
