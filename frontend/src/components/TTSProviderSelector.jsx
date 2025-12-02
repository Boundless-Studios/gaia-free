import React, { useState, useEffect } from 'react';
import apiService from '../services/apiService';
import { Button } from './base-ui/Button';

const TTSProviderSelector = ({ selectedProvider, onProviderChange, onRefresh }) => {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      
      // First check availability
      let _availabilityData = null;
      try {
        _availabilityData = await apiService.getTTSAvailability();
      } catch (err) {
        console.warn('Could not fetch TTS availability:', err);
      }
      
      // Then fetch providers with recommended default
      const data = await apiService.getTTSProviders();
      if (data) {
        const providers = data.providers || [];
        
        // Store the full response data for use in useEffect
        setData(data);
        
        setProviders(providers);
      } else {
        throw new Error('Failed to fetch TTS providers');
      }
    } catch (err) {
      console.error('Error fetching TTS providers:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  // Auto-select recommended provider when providers change
  useEffect(() => {
    if (providers.length > 0 && !selectedProvider) {
      // Use the recommended provider from the backend if available
      const recommendedProvider = providers.find(p => p.id === data?.recommended_provider);
      const preferredProvider = recommendedProvider || providers[0];
      if (preferredProvider) {
        console.log(`Auto-selecting provider: ${preferredProvider.id}`);
        onProviderChange(preferredProvider.id);
      }
    }
  }, [providers, selectedProvider, onProviderChange, data]);

  const handleProviderChange = (providerId) => {
    onProviderChange(providerId);
  };

  const handleRefresh = () => {
    fetchProviders();
    if (onRefresh) {
      onRefresh();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gaia-muted">Loading...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-red-400">Error</span>
        <Button onClick={handleRefresh} size="xs" variant="ghost" className="p-1">
          🔄
        </Button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <div className="flex gap-1">
        {providers.map(provider => (
          <Button
            key={provider.id}
            variant={selectedProvider === provider.id ? 'primary' : 'ghost'}
            size="xs"
            onClick={() => handleProviderChange(provider.id)}
            title={`Switch to ${provider.name} TTS`}
            className="flex items-center gap-1 px-2 py-1"
          >
            <span className="text-xs">{provider.icon}</span>
            <span className="text-xs">{provider.name}</span>
          </Button>
        ))}
      </div>
      {providers.length === 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gaia-muted">No TTS providers available</span>
          <Button onClick={handleRefresh} size="xs" variant="ghost" className="p-1">
            🔄
          </Button>
        </div>
      )}
    </div>
  );
};

export default TTSProviderSelector; 