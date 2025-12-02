import { useState, useCallback, useRef } from 'react';
import { API_CONFIG } from '../config/api.js';
import apiService from '../services/apiService.js';
import { generateUniqueId } from '../utils/idGenerator.js';

const IMAGE_DISMISS_TTL_MS = 60 * 1000; // 1 minute

/**
 * Custom hook to manage image generation and display
 * Handles image storage, popup display, dismissal tracking, and loading recent images
 *
 * @param {string} currentCampaignId - The active campaign ID
 * @returns {Object} Image management interface
 */
export function useImageManagement(currentCampaignId) {
  const [generatedImages, setGeneratedImages] = useState([]);
  const [showImagePopup, setShowImagePopup] = useState(false);
  const [currentPopupImage, setCurrentPopupImage] = useState(null);

  // Track which images have been shown and which have been dismissed
  const displayedImageUrlsRef = useRef(new Set());
  const dismissedImageKeysRef = useRef(new Map());

  /**
   * Handle new generated image
   * Manages popup display, dismissal tracking, and duplicate prevention
   *
   * @param {Object} imageData - Image data from backend
   * @param {boolean} forceShow - Force show popup even if already displayed
   */
  const handleNewImage = useCallback(
    (imageData, forceShow = false) => {
      if (!imageData) return;

      // Ensure we have a proper URL
      let fullImageUrl = imageData.generated_image_url;

      // If backend provided a direct image URL (e.g., /api/images/...), prefer it.
      // Fall back to session media route only when necessary.
      try {
        const provided = String(fullImageUrl || '');
        const isProvidedUsable = provided.startsWith('/api/images/') || provided.startsWith('http');
        if (!isProvidedUsable) {
          const filenameFromUrl = (() => {
            const raw = imageData.generated_image_url || imageData.generated_image_path || '';
            const last = String(raw).split('/').pop();
            return last && last.includes('.') ? last : null;
          })();
          if (currentCampaignId && filenameFromUrl) {
            fullImageUrl = `/api/media/${encodeURIComponent(currentCampaignId)}/images/${encodeURIComponent(filenameFromUrl)}`;
          }
        }
      } catch (_) {
        // Fallback to provided URL construction below
      }

      if (fullImageUrl && !fullImageUrl.startsWith('http')) {
        fullImageUrl = `${API_CONFIG.BACKEND_URL}${fullImageUrl}`;
      }

      const imageKey = fullImageUrl || imageData.generated_image_path || '';

      if (imageKey) {
        const dismissedMap = dismissedImageKeysRef.current;
        const now = Date.now();

        if (forceShow) {
          dismissedMap.delete(imageKey);
        } else {
          const dismissalExpiry = dismissedMap.get(imageKey);
          if (typeof dismissalExpiry === 'number') {
            if (dismissalExpiry > now) {
              console.log('handleNewImage - image dismissed by user, skipping popup:', imageKey);
              return;
            }
            dismissedMap.delete(imageKey);
          }
          if (displayedImageUrlsRef.current.has(imageKey)) {
            console.log('handleNewImage - image already displayed, skipping popup:', imageKey);
            return;
          }
        }

        displayedImageUrlsRef.current.add(imageKey);
        dismissedImageKeysRef.current.delete(imageKey);
      }

      const newImage = {
        id: generateUniqueId(),
        imageUrl: fullImageUrl,
        imagePath: imageData.generated_image_path,
        imagePrompt: imageData.generated_image_prompt,
        imageType: imageData.generated_image_type,
        timestamp: new Date().toISOString(),
        imageKey,
      };

      console.log('handleNewImage - created image object:', newImage);

      // Add to images array (only if not already there)
      setGeneratedImages((prev) => {
        const exists = prev.some((img) => {
          if (img.imageKey && newImage.imageKey) {
            return img.imageKey === newImage.imageKey;
          }
          return img.imageUrl === newImage.imageUrl;
        });
        if (exists) {
          return prev; // Don't add duplicates
        }
        return [newImage, ...prev];
      });

      // Show popup
      setCurrentPopupImage(newImage);
      setShowImagePopup(true);
    },
    [currentCampaignId]
  );

  /**
   * Handle clicked image from gallery
   * Forces popup to show even if image was previously dismissed
   */
  const handleImageClick = useCallback(
    (imageData) => {
      console.log('🖼️ handleImageClick called with:', imageData);
      // Force show the popup even if image was already displayed
      handleNewImage(imageData, true);
    },
    [handleNewImage]
  );

  /**
   * Close image popup
   * @param {string} reason - 'manual' if user closed, 'auto' if automatic
   */
  const handleImagePopupClose = useCallback((reason = 'auto') => {
    const now = Date.now();
    setCurrentPopupImage((previous) => {
      if (previous?.imageKey && reason === 'manual') {
        dismissedImageKeysRef.current.set(previous.imageKey, now + IMAGE_DISMISS_TTL_MS);
      }
      return null;
    });
    setShowImagePopup(false);
  }, []);

  /**
   * Load recent images from backend
   * @param {string} campaignId - Campaign ID to load images for
   */
  const loadRecentImages = useCallback(async (campaignId = null) => {
    if (!campaignId) {
      setGeneratedImages([]);
      return;
    }

    console.log('🖼️ Loading recent images...');
    const images = await apiService.fetchRecentImages(20, campaignId);

    if (images && images.length > 0) {
      console.log(`🖼️ Found ${images.length} recent images`);

      // Convert to the format expected by ImageGallery
      const formattedImages = images.map((img) => {
        // Extract a meaningful prompt from the filename
        let prompt = img.filename;

        // Handle gemini_image_TIMESTAMP.png format
        if (prompt.startsWith('gemini_image_')) {
          prompt = 'D&D Scene'; // Generic name for gemini images
        } else {
          // Remove common prefixes and suffixes
          prompt = prompt
            .replace(/^(gemini_image_|test_scroll_|\d+_)/, '')
            .replace(/\.(png|jpg|jpeg|webp)$/i, '')
            .replace(/_/g, ' ')
            .replace(/\d{10,}/g, '') // Remove timestamps
            .trim();
        }

        // If prompt is empty or just numbers, use generic name
        if (!prompt || /^\d+$/.test(prompt)) {
          prompt = 'D&D Scene';
        }

        return {
          id: img.filename,
          imageUrl: `${API_CONFIG.BACKEND_URL}${img.path}`,
          imagePath: img.filename,
          imagePrompt: prompt,
          timestamp: img.timestamp,
        };
      });

      // Add all images to the generatedImages state
      setGeneratedImages(formattedImages);

      // Mark all images as already displayed to prevent automatic popups
      formattedImages.forEach((img) => {
        displayedImageUrlsRef.current.add(img.imageUrl);
      });
    }
  }, []);

  return {
    // State
    images: generatedImages,
    showPopup: showImagePopup,
    currentPopupImage,

    // Operations
    handleNewImage,
    handleImageClick,
    closePopup: handleImagePopupClose,
    loadRecent: loadRecentImages,

    // Refs (for advanced use cases)
    displayedImagesRef: displayedImageUrlsRef,
    dismissedImagesRef: dismissedImageKeysRef,
  };
}
