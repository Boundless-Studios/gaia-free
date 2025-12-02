import { useCallback } from 'react';
import apiService from '../services/apiService.js';
import { generateUniqueId } from '../utils/idGenerator.js';

/**
 * Custom hook to manage campaign operations (CRUD, loading, selection)
 * Handles the complex logic of campaign selection, creation, and state management
 *
 * @param {Object} params - Configuration object
 * @returns {Object} Campaign operations interface
 */
export function useCampaignOperations({
  currentCampaignId,
  setCurrentCampaignId,
  setPendingInitialNarrative,
  setSessionNeedsResume,
  setSessionMessages,
  setSessionStructuredData,
  setSessionHistoryInfo,
  setIsLoading,
  setError,
  setShowCampaignList,
  transformStructuredData,
  loadRecentImages,
  markLastDmMessageHasAudio,
  handleNewImage,
  updateStreamingNarrative,
  updateStreamingResponse,
  clearStreaming,
  setCampaignName, // Add setCampaignName here
}) {
  /**
   * Select and load a campaign
   * This is the main campaign loading function - handles all state setup
   *
   * @param {string} campaignId - Campaign ID to load
   * @param {boolean} isNewCampaign - Whether this is a newly created campaign
   */
  const handleSelectCampaign = useCallback(
    async (campaignId, isNewCampaign = false) => {
      console.log('🎮 Selecting campaign:', campaignId, 'isNew:', isNewCampaign);

      // Don't set currentCampaignId until we successfully load the campaign
      setShowCampaignList(false);

      if (!campaignId) {
        return;
      }
      const sessionId = campaignId;

      if (isNewCampaign) {
        setPendingInitialNarrative(sessionId, true);
        setSessionNeedsResume(sessionId, false);
        setIsLoading(true);
      } else {
        setPendingInitialNarrative(sessionId, false);
        setIsLoading(false);
      }

      await loadRecentImages(campaignId);

      try {
        const data = await apiService.loadSimpleCampaign(campaignId);
        if (!data) {
          console.error('Failed to load simple campaign');
          const error = new Error('Failed to load simple campaign');
          setError(error.message);
          throw error;
        }

        console.log('🎮 Loaded simple campaign:', data);

        if (!data.success || !data.activated) {
          console.error('Failed to activate simple campaign');
          const error = new Error('Failed to activate simple campaign');
          setError(error.message);
          throw error;
        }

        const structuredData = data.structured_data;
        if (structuredData) {
          console.log('🎮 Received structured data from simple campaign:', structuredData);
          const transformedData = transformStructuredData(structuredData, {
            needsResponse: Boolean(data.needs_response),
            sessionId,
          });
          if (transformedData) {
            setSessionStructuredData(sessionId, transformedData);
            setCampaignName(data.name || campaignId); // Set campaign name here
            // Audio now handled by synchronized streaming via WebSocket
            if (
              isNewCampaign &&
              (typeof updateStreamingNarrative === 'function' || typeof updateStreamingResponse === 'function')
            ) {
              if (typeof clearStreaming === 'function') {
                clearStreaming(sessionId);
              }
              const narrativeText = (transformedData.narrative || '').trim();
              if (narrativeText && typeof updateStreamingNarrative === 'function') {
                updateStreamingNarrative(sessionId, narrativeText, {
                  append: false,
                  isStreaming: false,
                  isFinal: true,
                });
              }
              const playerResponseText = (transformedData.player_response || '').trim();
              const fallbackAnswerText = (transformedData.answer || '').trim();
              const responseText = playerResponseText || (!narrativeText && fallbackAnswerText ? fallbackAnswerText : '');
              if (responseText && typeof updateStreamingResponse === 'function') {
                updateStreamingResponse(sessionId, responseText, {
                  append: false,
                  isStreaming: false,
                  isFinal: true,
                });
              }
            }
          } else {
            setSessionStructuredData(sessionId, null);
          }
        } else {
          setSessionStructuredData(sessionId, null);
        }

        if (data.history_info) {
          setSessionHistoryInfo(sessionId, data.history_info);
          setTimeout(() => setSessionHistoryInfo(sessionId, null), 10000);
        } else {
          setSessionHistoryInfo(sessionId, null);
        }

        let convertedMessages = [];
        if (data.messages) {
          convertedMessages = data.messages.map((msg, index) => {
            let text = msg.content;
            let structuredContent = null;

            if (msg.role === 'assistant' && typeof msg.content === 'object') {
              // Store both narrative and answer in structured content
              structuredContent = {
                narrative: msg.content.narrative || null,
                answer: msg.content.answer || null,
              };
              // Fallback text for backwards compatibility
              text = msg.content.answer || msg.content.narrative || JSON.stringify(msg.content);
            } else if (typeof msg.content !== 'string') {
              text = JSON.stringify(msg.content);
            }

            return {
              id: generateUniqueId(),
              text,
              structuredContent,
              sender: msg.role === 'assistant' ? 'dm' : msg.role,
              timestamp: msg.timestamp || new Date().toISOString(),
            };
          });
          setSessionMessages(sessionId, convertedMessages);
        } else {
          setSessionMessages(sessionId, []);
        }

        if (!isNewCampaign) {
          const systemMessage = {
            id: generateUniqueId(),
            text: `Loaded simple campaign: ${campaignId} (${data.message_count} messages)${structuredData ? ' - Game state loaded' : ''}`,
            sender: 'system',
            timestamp: new Date().toISOString(),
          };
          setSessionMessages(sessionId, (prev) => [systemMessage, ...prev]);
        }

        const hasDmMessage = convertedMessages.some((msg) => msg.sender === 'dm');
        if (isNewCampaign && !hasDmMessage) {
          setSessionNeedsResume(sessionId, false);
          setPendingInitialNarrative(sessionId, true);
          setIsLoading(true);
        } else {
          setSessionNeedsResume(
            sessionId,
            Boolean(data.needs_response) && (hasDmMessage || !isNewCampaign)
          );
          setPendingInitialNarrative(sessionId, false);
          setIsLoading(false);
        }

        // Only set currentCampaignId after successful load
        setCurrentCampaignId(campaignId);

        return data; // Return the loaded campaign data
      } catch (error) {
        console.error('Error loading simple campaign:', error);
        setError(`Failed to load simple campaign: ${error.message}`);

        // On error, set to null - URL is source of truth, no restore attempt
        setCurrentCampaignId(null);
        setPendingInitialNarrative(sessionId, false);
        setIsLoading(false);

        // Re-throw error so caller's .catch() block can handle it
        throw error;
      }
    },
    [
      currentCampaignId,
      setCurrentCampaignId,
      setShowCampaignList,
      setPendingInitialNarrative,
      setSessionNeedsResume,
      setIsLoading,
      loadRecentImages,
      setError,
      transformStructuredData,
      setSessionStructuredData,
      markLastDmMessageHasAudio,
      setSessionHistoryInfo,
      setSessionMessages,
      updateStreamingNarrative,
      updateStreamingResponse,
      clearStreaming,
    ]
  );

  /**
   * Create a blank campaign
   * Prompts user for confirmation, then creates new campaign
   */
  const createBlankCampaign = useCallback(async () => {
    const confirmReset = window.confirm(
      '📋 Create Blank Campaign?\n\n' +
        'This will create a new empty campaign.\n\n' +
        'Continue?'
    );

    if (!confirmReset) {
      return;
    }

    setIsLoading(true);

    try {
      const result = await apiService.sendBlankCampaignRequest();
      console.log('📋 Blank campaign created:', result);

      const campaignId = result.campaign_id || result.session_id;
      if (campaignId) {
        await handleSelectCampaign(campaignId, true);
        console.log('📋 Blank campaign activated');
      } else {
        setError('Failed to create blank campaign - no campaign ID returned');
        setIsLoading(false);
      }
    } catch (error) {
      console.error('❌ Failed to create blank campaign:', error);
      setError(`Failed to create blank campaign: ${error.message}`);
      setIsLoading(false);
    }
  }, [setIsLoading, setError, handleSelectCampaign]);

  /**
   * Quick start an arena combat
   * Creates a pre-configured arena battle scenario
   */
  const startArenaQuickStart = useCallback(async () => {
    try {
      setIsLoading(true);

      const response = await apiService.createArenaQuickStart();
      console.log('⚔️ Arena quick start response:', response);

      if (response.success && response.campaign_id) {
        // Load the created campaign
        await handleSelectCampaign(response.campaign_id, true);

        // Show success message
        console.log('✅ Arena campaign created and loaded');
      } else {
        throw new Error('Failed to create arena campaign');
      }
    } catch (error) {
      console.error('❌ Arena quick start failed:', error);
      setError(`Failed to start arena: ${error.message}`);
      setIsLoading(false);
    }
  }, [setIsLoading, setError, handleSelectCampaign]);


  /**
   * Join a shared session via invite token
   * @param {string} inviteToken - The invite token from URL
   */
  const joinSharedSession = useCallback(
    async (inviteToken) => {
      if (!inviteToken) {
        return;
      }

      console.log('🔗 Joining shared session with token:', inviteToken);
      try {
        const response = await apiService.joinSessionByInvite(inviteToken);
        console.log('✅ Successfully joined shared session:', response);
        await handleSelectCampaign(response.session_id, true);
        return { success: true, message: 'Successfully joined shared session.' };
      } catch (err) {
        console.error('Failed to join session via invite:', err);
        return {
          success: false,
          error: `Failed to join shared session: ${err.message}`,
        };
      }
    },
    [handleSelectCampaign]
  );

  return {
    selectCampaign: handleSelectCampaign,
    createBlankCampaign,
    startArenaQuickStart,
    joinSharedSession,
  };
}
