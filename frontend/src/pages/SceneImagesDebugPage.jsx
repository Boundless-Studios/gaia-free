import React, { useState, useCallback, useEffect, useRef } from 'react';
import { API_CONFIG } from '../config/api.js';
import SceneImageTrio from '../components/SceneImageTrio.jsx';

/**
 * SceneImagesDebugPage - Debug page for testing the Visual Narrator and scene image generation
 *
 * Features:
 * - Trigger visual narrator with a custom scene description
 * - View generated scene image descriptions
 * - Monitor image generation progress
 * - Display generated images
 */
const SceneImagesDebugPage = () => {
  // Form state
  const [campaignId, setCampaignId] = useState('debug_campaign_' + Date.now());
  const [sceneDescription, setSceneDescription] = useState(
    'The party enters a dimly lit tavern. Smoke curls from a fireplace in the corner. ' +
    'Rough-looking patrons huddle over drinks at scarred wooden tables. ' +
    'A bard strums a melancholy tune on a lute near the bar.'
  );
  const [turnNumber, setTurnNumber] = useState(1);

  // Generation state
  const [isGenerating, setIsGenerating] = useState(false);
  const [currentSetId, setCurrentSetId] = useState(null);
  const [generationResult, setGenerationResult] = useState(null);
  const [error, setError] = useState(null);

  // Image set state
  const [imageSet, setImageSet] = useState(null);
  const [pollingActive, setPollingActive] = useState(false);
  const pollingIntervalRef = useRef(null);

  // Logs
  const [logs, setLogs] = useState([]);

  const addLog = useCallback((message, level = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [...prev, { timestamp, message, level }]);
  }, []);

  // Trigger generation
  const handleGenerateClick = async () => {
    setError(null);
    setIsGenerating(true);
    setGenerationResult(null);
    setImageSet(null);
    setCurrentSetId(null);
    addLog('Starting scene image generation...');

    try {
      const response = await fetch(`${API_CONFIG.BACKEND_URL}/api/scene-images/test-generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          campaign_id: campaignId,
          scene_description: sceneDescription,
          turn_number: turnNumber,
        }),
      });

      const result = await response.json();
      addLog(`Response received: ${JSON.stringify(result)}`, result.success ? 'success' : 'error');

      if (result.success) {
        setGenerationResult(result);
        setCurrentSetId(result.set_id);
        addLog(`Visual narrator descriptions generated. Set ID: ${result.set_id}`, 'success');

        if (result.descriptions) {
          addLog(`Location: ${result.descriptions.location_ambiance || '(empty)'}`, 'info');
          addLog(`Background: ${result.descriptions.background_detail || '(empty)'}`, 'info');
          addLog(`Moment: ${result.descriptions.moment_focus || '(empty)'}`, 'info');
        }

        // Start polling for image generation status
        setPollingActive(true);
      } else {
        setError(result.message || 'Generation failed');
        addLog(`Generation failed: ${result.message}`, 'error');
      }
    } catch (err) {
      setError(err.message);
      addLog(`Error: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Poll for image generation status
  const pollImageSet = useCallback(async () => {
    if (!currentSetId) return;

    try {
      const response = await fetch(
        `${API_CONFIG.BACKEND_URL}/api/scene-images/${currentSetId}`
      );

      if (response.ok) {
        const data = await response.json();
        setImageSet(data);

        // Log status updates
        const statusMap = {};
        data.images?.forEach(img => {
          statusMap[img.type] = img.status;
        });
        addLog(`Status: ${JSON.stringify(statusMap)}`, 'info');

        // Stop polling if complete or failed
        if (data.status === 'complete' || data.status === 'failed') {
          addLog(`Generation ${data.status}!`, data.status === 'complete' ? 'success' : 'error');
          setPollingActive(false);
        }
      }
    } catch (err) {
      addLog(`Polling error: ${err.message}`, 'error');
    }
  }, [currentSetId, addLog]);

  // Polling effect
  useEffect(() => {
    if (pollingActive && currentSetId) {
      // Initial poll
      pollImageSet();

      // Set up interval
      pollingIntervalRef.current = setInterval(pollImageSet, 2000);

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }
  }, [pollingActive, currentSetId, pollImageSet]);

  // Clear polling on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, []);

  const getStatusBadge = (status) => {
    const styles = {
      pending: 'bg-gray-100 text-gray-800',
      generating: 'bg-yellow-100 text-yellow-800',
      complete: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const getLogStyle = (level) => {
    const styles = {
      info: 'text-gray-700',
      success: 'text-green-700',
      error: 'text-red-700',
    };
    return styles[level] || 'text-gray-700';
  };

  // Render image card
  const renderImageCard = (image) => {
    const typeLabels = {
      location_ambiance: 'Location Ambiance',
      background_detail: 'Background Detail',
      moment_focus: 'Moment Focus',
    };

    return (
      <div
        key={image.type}
        className="bg-white rounded-lg border border-gray-200 overflow-hidden"
        data-testid={`image-card-${image.type}`}
      >
        {/* Card Header */}
        <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <span className="font-semibold text-gray-900">{typeLabels[image.type] || image.type}</span>
          <span
            className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(image.status)}`}
            data-testid={`status-${image.type}`}
          >
            {image.status}
          </span>
        </div>

        {/* Description - with better readability */}
        <div className="px-4 py-3 border-b border-gray-200 min-h-[80px]">
          <p className="text-sm text-gray-600 leading-relaxed">
            {image.description || '(No description)'}
          </p>
        </div>

        {/* Image Preview */}
        <div
          className="aspect-video bg-gray-100 flex items-center justify-center"
          data-testid={`preview-${image.type}`}
        >
          {image.status === 'pending' || image.status === 'generating' ? (
            <div className="flex flex-col items-center gap-2 text-gray-500">
              <div className="w-8 h-8 border-3 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
              <span className="text-sm">Generating...</span>
            </div>
          ) : image.status === 'failed' ? (
            <div className="flex flex-col items-center gap-2 text-red-500 p-4 text-center">
              <span className="text-2xl">&#9888;</span>
              <span className="text-sm">{image.error || 'Generation failed'}</span>
            </div>
          ) : image.image_url ? (
            <img
              src={`${API_CONFIG.BACKEND_URL}${image.image_url}`}
              alt={image.description}
              className="w-full h-full object-cover"
              data-testid={`image-${image.type}`}
            />
          ) : (
            <span className="text-sm text-gray-400">No image URL</span>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="scene-images-debug-page">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">Scene Images Debug</h1>
        <p className="text-sm text-gray-500 mt-1">
          Test the Visual Narrator agent and scene image generation pipeline
        </p>
      </div>

      <div className="p-6 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column - Input Form */}
          <div className="space-y-6">
            {/* Input Form */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                <h2 className="text-lg font-semibold text-gray-900">Generate Scene Images</h2>
              </div>
              <div className="p-4 space-y-4">
                {/* Campaign ID */}
                <div>
                  <label htmlFor="campaignId" className="block text-sm font-medium text-gray-700 mb-1">
                    Campaign ID
                  </label>
                  <input
                    id="campaignId"
                    type="text"
                    value={campaignId}
                    onChange={(e) => setCampaignId(e.target.value)}
                    placeholder="Enter campaign ID"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="campaign-id-input"
                  />
                </div>

                {/* Turn Number */}
                <div>
                  <label htmlFor="turnNumber" className="block text-sm font-medium text-gray-700 mb-1">
                    Turn Number
                  </label>
                  <input
                    id="turnNumber"
                    type="number"
                    value={turnNumber}
                    onChange={(e) => setTurnNumber(parseInt(e.target.value) || 1)}
                    min="1"
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    data-testid="turn-number-input"
                  />
                </div>

                {/* Scene Description - with more space */}
                <div>
                  <label htmlFor="sceneDescription" className="block text-sm font-medium text-gray-700 mb-1">
                    Scene Description
                  </label>
                  <textarea
                    id="sceneDescription"
                    value={sceneDescription}
                    onChange={(e) => setSceneDescription(e.target.value)}
                    rows={8}
                    placeholder="Enter a detailed scene description..."
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed"
                    data-testid="scene-description-input"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    {sceneDescription.length} characters
                  </p>
                </div>

                {/* Generate Button */}
                <button
                  onClick={handleGenerateClick}
                  disabled={isGenerating || !sceneDescription.trim()}
                  className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  data-testid="generate-button"
                >
                  {isGenerating ? 'Generating...' : 'Generate Scene Images'}
                </button>

                {error && (
                  <div
                    className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-800"
                    data-testid="error-message"
                  >
                    {error}
                  </div>
                )}
              </div>
            </div>

            {/* Logs Section */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">Logs</h2>
                <button
                  onClick={() => setLogs([])}
                  className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-200 rounded transition-colors"
                >
                  Clear
                </button>
              </div>
              <div
                className="p-2 max-h-[300px] overflow-y-auto font-mono text-xs bg-gray-50"
                data-testid="logs-container"
              >
                {logs.length === 0 ? (
                  <div className="text-center text-gray-400 py-4">No logs yet</div>
                ) : (
                  logs.map((log, index) => (
                    <div key={index} className="px-2 py-1 hover:bg-gray-100 rounded flex gap-2">
                      <span className="text-gray-400 flex-shrink-0">{log.timestamp}</span>
                      <span className={`break-all ${getLogStyle(log.level)}`}>{log.message}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Results */}
          <div className="space-y-6">
            {/* Scene Image Trio - Framed Display */}
            {imageSet && (
              <div className="bg-gray-900 rounded-lg p-6" data-testid="trio-section">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-white">Scene Triptych</h2>
                  {imageSet && (
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(imageSet.status)}`}
                    >
                      {imageSet.status}
                    </span>
                  )}
                </div>
                <SceneImageTrio
                  imageSet={imageSet}
                  size="large"
                  showLabels={true}
                  showDescriptions={true}
                  onImageClick={(image) => {
                    addLog(`Clicked: ${image.type}`, 'info');
                  }}
                />
              </div>
            )}

            {/* Detailed Results Section */}
            {(generationResult || imageSet) ? (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden" data-testid="results-section">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-gray-900">Detailed Results</h2>
                  {imageSet && (
                    <span
                      className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(imageSet.status)}`}
                      data-testid="set-status"
                    >
                      {imageSet.status}
                    </span>
                  )}
                </div>

                {currentSetId && (
                  <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs text-gray-500">
                    Set ID: <span className="font-mono">{currentSetId}</span>
                  </div>
                )}

                <div className="p-4">
                  {imageSet?.images ? (
                    <div className="space-y-4" data-testid="images-grid">
                      {imageSet.images.map(renderImageCard)}
                    </div>
                  ) : (
                    <div className="text-center text-gray-400 py-8">
                      Waiting for image generation...
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Generation Results</h2>
                </div>
                <div className="p-8 text-center text-gray-400">
                  <p className="text-lg mb-2">&#127912;</p>
                  <p>Enter a scene description and click "Generate" to create images</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SceneImagesDebugPage;
