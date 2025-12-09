import React, { createContext, useContext, useState } from 'react';

// Loading context for managing global loading states
const LoadingContext = createContext();

// Loading state types
export const LoadingTypes = {
  IMAGE_GENERATION: 'imageGeneration',
  TTS_GENERATION: 'ttsGeneration', 
  MODEL_LOADING: 'modelLoading'
};

// Loading provider component
export const LoadingProvider = ({ children }) => {
  const [loadingStates, setLoadingStates] = useState({
    [LoadingTypes.IMAGE_GENERATION]: false,
    [LoadingTypes.TTS_GENERATION]: false,
    [LoadingTypes.MODEL_LOADING]: false
  });

  // Track queue counts for each loading type
  const [queueCounts, setQueueCounts] = useState({
    [LoadingTypes.IMAGE_GENERATION]: 0,
    [LoadingTypes.TTS_GENERATION]: 0,
    [LoadingTypes.MODEL_LOADING]: 0
  });

  // Set loading state for a specific type (with optional queue count)
  const setLoading = (type, isLoading, queueCount = 0) => {
    setLoadingStates(prev => ({
      ...prev,
      [type]: isLoading
    }));
    setQueueCounts(prev => ({
      ...prev,
      [type]: queueCount
    }));
  };

  // Get queue count for a specific type
  const getQueueCount = (type) => {
    return queueCounts[type] || 0;
  };

  // Check if any loading is active
  const isAnyLoading = () => {
    return Object.values(loadingStates).some(isLoading => isLoading);
  };

  // Get active loading types
  const getActiveLoadings = () => {
    return Object.entries(loadingStates)
      .filter(([_, isLoading]) => isLoading)
      .map(([type, _]) => type);
  };

  const value = {
    loadingStates,
    queueCounts,
    setLoading,
    getQueueCount,
    isAnyLoading,
    getActiveLoadings
  };

  return (
    <LoadingContext.Provider value={value}>
      {children}
    </LoadingContext.Provider>
  );
};

// Custom hook to use loading context
export const useLoading = () => {
  const context = useContext(LoadingContext);
  if (!context) {
    throw new Error('useLoading must be used within a LoadingProvider');
  }
  return context;
};

export default LoadingContext;
