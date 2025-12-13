import React, { useState, useRef, useEffect, useCallback } from 'react';
import { API_CONFIG } from '../config/api.js';
import apiService from '../services/apiService';
import { Button } from './base-ui/Button';

const ImageGalleryWithPolling = ({ maxImages = 20, pollingInterval = 10000, campaignId = null, onImageClick = null }) => {
  const [images, setImages] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [isLoading, _setIsLoading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [startX, setStartX] = useState(0);
  const [scrollLeft, setScrollLeft] = useState(0);
  const scrollContainerRef = useRef(null);
  const pollingIntervalRef = useRef(null);
  const processedImageIds = useRef(new Set());
  const [isPageVisible, setIsPageVisible] = useState(
    typeof document === 'undefined' ? true : document.visibilityState === 'visible'
  );
  
  // Fetch images from API with graceful error handling
  const fetchImages = useCallback(async () => {
    if (!campaignId) {
      setImages([]);
      return;
    }

    try {
      const data = await apiService.fetchRecentImages(maxImages, campaignId);
      
      if (data && Array.isArray(data)) {
        console.log(`🖼️ Fetched ${data.length} images from API`);
        
        // Process and deduplicate images
        const newImages = data
          .filter(img => img && img.filename)
          .map(img => {
            // Prefer server-provided path to ensure correct routing/auth
            const fallbackPath = `/api/images/${encodeURIComponent(img.filename)}`;
            const path = img.proxy_url || img.path || fallbackPath;
            return {
              id: img.filename,
              imageUrl: `${API_CONFIG.BACKEND_URL}${path}`,
              imagePath: img.filename,
              imagePrompt: img.prompt || extractPromptFromFilename(img.filename),
              timestamp: img.timestamp || new Date(img.modified * 1000).toISOString(),
              size: img.size,
              type: img.type || 'scene',
              model: img.model || 'unknown'
            };
          })
          .filter(img => {
            // Filter out already processed images
            if (processedImageIds.current.has(img.id)) {
              return true; // Keep existing images
            }
            processedImageIds.current.add(img.id);
            return true;
          });
        
        setImages(newImages);
      }
    } catch (error) {
      // Log errors for debugging
      console.error('🖼️ Error fetching images:', error);
    }
  }, [campaignId, maxImages]);
  
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
  
  // Track page visibility so we can pause polling when the tab is hidden
  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const handleVisibility = () => {
      setIsPageVisible(document.visibilityState === 'visible');
    };

    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  // Start polling when component mounts, pausing automatically when tab hidden
  useEffect(() => {
    if (!isPageVisible) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    console.log('ImageGalleryWithPolling mounted, starting polling...');

    // Fire an immediate fetch so the UI updates as soon as tab becomes visible
    fetchImages();

    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }

    pollingIntervalRef.current = setInterval(() => {
      fetchImages();
    }, pollingInterval);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [pollingInterval, fetchImages, isPageVisible]);
  
  // Handle horizontal scroll with mouse wheel
  useEffect(() => {
    const handleWheel = (e) => {
      const container = scrollContainerRef.current;
      if (!container) return;
      
      // Check if the event target is within our container
      if (!container.contains(e.target)) return;
      
      // Prevent default vertical scroll
      e.preventDefault();
      
      // Convert vertical scroll to horizontal
      const scrollAmount = e.deltaY;
      container.scrollLeft += scrollAmount;
    };
    
    // Add to document to ensure we catch all wheel events
    document.addEventListener('wheel', handleWheel, { passive: false });
    
    return () => {
      document.removeEventListener('wheel', handleWheel);
    };
  }, []); // Empty deps, never re-attach
  
  // Handle drag scrolling
  const handleMouseDown = (e) => {
    const container = scrollContainerRef.current;
    if (!container) return;
    
    setIsDragging(true);
    setStartX(e.pageX - container.offsetLeft);
    setScrollLeft(container.scrollLeft);
    container.style.cursor = 'grabbing';
  };
  
  const handleMouseUp = () => {
    setIsDragging(false);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.style.cursor = 'grab';
    }
  };
  
  const handleMouseMove = (e) => {
    if (!isDragging) return;
    e.preventDefault();
    
    const container = scrollContainerRef.current;
    if (!container) return;
    
    const x = e.pageX - container.offsetLeft;
    const walk = (x - startX) * 2; // Multiply by 2 for faster scrolling
    container.scrollLeft = scrollLeft - walk;
  };
  
  const handleMouseLeave = () => {
    setIsDragging(false);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.style.cursor = 'grab';
    }
  };
  
  // Auto-scroll to show new images only on first load
  useEffect(() => {
    if (images.length > 0 && scrollContainerRef.current && processedImageIds.current.size <= images.length) {
      // Only auto-scroll on initial load or if user is already at the left edge
      const container = scrollContainerRef.current;
      if (container.scrollLeft < 50) {
        container.scrollTo({
          left: 0,
          behavior: 'smooth'
        });
      }
    }
  }, [images.length]);
  
  // Handle escape key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && selectedImage) {
        setSelectedImage(null);
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [selectedImage]);

  // Custom styles for scrollbar
  const scrollbarStyles = `
    .gallery-scrollbar::-webkit-scrollbar {
      height: 6px;
    }
    .gallery-scrollbar::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.2);
      border-radius: 3px;
    }
    .gallery-scrollbar::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.2);
      border-radius: 3px;
    }
    .gallery-scrollbar::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.3);
    }
    @keyframes spin {
      from { transform: rotate(0deg); }
      to { transform: rotate(360deg); }
    }
    .animate-spin-custom {
      animation: spin 1s linear infinite;
    }
  `;
  
  if (images.length === 0) {
    return (
      <>
        <style>{scrollbarStyles}</style>
        <div className="bg-gaia-light/60 border border-white/10 rounded-lg p-3 backdrop-blur-md h-full flex flex-col">
          <div className="flex items-center gap-2 mb-2 text-gray-200">
            <span className="text-lg">🖼️</span>
            <h3 className="m-0 text-sm font-semibold flex-1">Scene Gallery</h3>
            {isLoading && <span className="text-gaia-accent ml-2 inline-block animate-spin-custom">🔄</span>}
          </div>
          <div className="flex-1 flex flex-col items-center justify-center text-gray-500 italic gap-2">
            <p>No scenes generated yet</p>
            <p className="text-xs text-gray-600">Images will appear here automatically</p>
          </div>
        </div>
      </>
    );
  }
  
  return (
    <>
      <style>{scrollbarStyles}</style>
      <div className="bg-gaia-light/60 border border-white/10 rounded-lg p-3 backdrop-blur-md h-full flex flex-col">
        <div className="flex items-center gap-2 mb-2 text-gray-200">
          <span className="text-lg">🖼️</span>
          <h3 className="m-0 text-sm font-semibold flex-1">Scene Gallery</h3>
          <span className="text-xs text-gray-400 bg-white/10 px-2 py-0.5 rounded-full">{images.length} scenes</span>
          {isLoading && <span className="text-gaia-accent ml-2 inline-block animate-spin-custom">🔄</span>}
        </div>
        <div 
          className="gallery-scrollbar flex-1 overflow-x-auto overflow-y-hidden relative scroll-smooth group"
          ref={scrollContainerRef}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          style={{ 
            cursor: isDragging ? 'grabbing' : 'grab',
            scrollbarWidth: 'thin',
            scrollbarColor: 'rgba(255, 255, 255, 0.2) transparent'
          }}
        >
          {/* Scroll hint that appears on hover */}
          <div className="absolute bottom-2 right-2 text-xs text-white/60 bg-black/80 px-2.5 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
            Use mouse wheel to scroll →
          </div>
          
          <div className="flex gap-3 h-full items-center">
            {images.map((image, index) => {
              // Detect composite images (3x wider)
              const isComposite = image.id?.includes('composite_') || image.imagePath?.includes('composite_');
              const imageWidth = isComposite ? 'w-[912px]' : 'w-[300px]';

              return (
              <div
                key={image.id}
                className={`relative flex-shrink-0 h-[300px] ${imageWidth} cursor-pointer rounded-md overflow-hidden transition-all duration-200 border-2 hover:-translate-y-0.5 hover:shadow-xl hover:border-orange-500/50 ${
                  index === 0 ? 'border-orange-500/30' : 'border-transparent'
                }`}
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('🖼️ Image clicked:', image.imagePrompt);
                  console.log('🖼️ isDragging:', isDragging);
                  console.log('🖼️ onImageClick prop:', !!onImageClick);
                  
                  // Always reset dragging state on click to prevent stuck state
                  setIsDragging(false);
                  
                  // Use main App modal if onImageClick is provided, otherwise use internal modal
                  if (onImageClick) {
                    console.log('🖼️ Using main App modal via onImageClick');
                    onImageClick({
                      generated_image_url: image.imageUrl,
                      generated_image_path: image.imagePath,
                      generated_image_prompt: image.imagePrompt,
                      generated_image_type: image.imageType || 'scene'
                    });
                  } else {
                    console.log('🖼️ Using internal modal, setSelectedImage');
                    setSelectedImage(image);
                  }
                }}
                title={`${image.imagePrompt}\nClick to view full size`}
                style={{ userSelect: isDragging ? 'none' : 'auto' }}
              >
                <img 
                  src={image.imageUrl} 
                  alt={image.imagePrompt}
                  className="w-full h-full object-cover block bg-gray-800"
                  loading="lazy"
                  draggable="false"
                  onError={(e) => {
                    console.error(`Failed to load image:`, e.target.src);
                    e.target.style.display = 'none';
                  }}
                />
                {index === 0 && (
                  <span className="absolute top-2 right-2 bg-orange-500/80 text-white px-3 py-1 rounded-md text-xs font-bold uppercase">
                    Latest
                  </span>
                )}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-4 opacity-0 hover:opacity-100 transition-opacity duration-200">
                  <span className="text-white text-sm leading-relaxed line-clamp-3">
                    {image.imagePrompt}
                  </span>
                  {image.size && (
                    <span className="text-white/70 text-xs mt-1 block">
                      {(image.size / 1024).toFixed(1)} KB
                    </span>
                  )}
                </div>
              </div>
              )
            })}
          </div>
        </div>
        
        {/* Full-size image modal */}
        {selectedImage && (
          <div 
            className="fixed inset-0 bg-black/90 flex items-center justify-center z-[9999] cursor-pointer"
            onClick={() => setSelectedImage(null)}
          >
            <div 
              className="relative max-w-[90vw] max-h-[90vh] cursor-default"
              onClick={(e) => e.stopPropagation()}
            >
              <Button 
                className="absolute -top-10 right-0 w-10 h-10 bg-white/10 text-white border-none rounded-full text-2xl cursor-pointer flex items-center justify-center transition-colors hover:bg-orange-500/80"
                onClick={() => setSelectedImage(null)}
                variant="ghost"
              >
                ×
              </Button>
              <img 
                src={selectedImage.imageUrl} 
                alt={selectedImage.imagePrompt}
                className="w-full h-full object-contain rounded-lg"
              />
              {selectedImage.imagePrompt && (
                <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white p-4 text-sm text-center rounded-b-lg">
                  {selectedImage.imagePrompt}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default ImageGalleryWithPolling;
