import React from 'react';
import { useLoading, LoadingTypes } from '../contexts/LoadingContext';

const UnifiedLoadingIndicator = () => {
  const { getActiveLoadings, getQueueCount } = useLoading();

  const activeLoadings = getActiveLoadings();

  // Don't render if no loading is active
  if (activeLoadings.length === 0) {
    return null;
  }

  // Map loading types to display names with queue counts
  const getDisplayName = (type) => {
    const queueCount = getQueueCount(type);
    let name;

    switch(type) {
      case LoadingTypes.IMAGE_GENERATION:
        name = 'Image';
        break;
      case LoadingTypes.TTS_GENERATION:
        name = 'TTS';
        break;
      case LoadingTypes.MODEL_LOADING:
        name = 'Model';
        break;
      default:
        name = type;
    }

    // Append queue count if > 0
    if (queueCount > 0) {
      return `${name} • ${queueCount} queued`;
    }
    return name;
  };

  // Create comma-separated list of active loadings
  const loadingText = activeLoadings
    .map(getDisplayName)
    .join(', ');

  return (
    <div className="flex items-center gap-1.5 text-white text-sm font-medium">
      <div className="inline-block w-2.5 h-2.5 border-[1.5px] border-white/30 border-t-white rounded-full animate-spin"></div>
      <span className="text-gray-200 whitespace-nowrap">Loading {loadingText}</span>
    </div>
  );
};

export default UnifiedLoadingIndicator;
