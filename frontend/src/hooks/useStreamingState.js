import { useState, useCallback, useRef, useEffect } from 'react';
import { loggers } from '../utils/logger.js';

const log = loggers.streaming;

/**
 * Custom hook to manage streaming message state per session
 * Handles both narrative and response streaming with refs for callback access
 *
 * @param {string} currentCampaignId - The active campaign ID
 * @returns {Object} Streaming state management interface
 */
export function useStreamingState(currentCampaignId) {
  // Streaming content state
  const [dmStreamingNarrativeBySession, setDmStreamingNarrativeBySession] = useState({});
  const [dmStreamingResponseBySession, setDmStreamingResponseBySession] = useState({});

  // Streaming active flags
  const [dmIsNarrativeStreamingBySession, setDmIsNarrativeStreamingBySession] = useState({});
  const [dmIsResponseStreamingBySession, setDmIsResponseStreamingBySession] = useState({});

  // Refs for callback access to latest state
  const dmIsNarrativeStreamingRef = useRef(dmIsNarrativeStreamingBySession);
  const dmIsResponseStreamingRef = useRef(dmIsResponseStreamingBySession);

  // Keep refs in sync
  useEffect(() => {
    dmIsNarrativeStreamingRef.current = dmIsNarrativeStreamingBySession;
  }, [dmIsNarrativeStreamingBySession]);

  useEffect(() => {
    dmIsResponseStreamingRef.current = dmIsResponseStreamingBySession;
  }, [dmIsResponseStreamingBySession]);

  /**
   * Update streaming narrative content
   * Supports appending chunks or replacing content
   */
  const updateStreamingNarrative = useCallback(
    (sessionId, content, { append, isStreaming = true, isFinal = false } = {}) => {
      if (!sessionId) {
        return;
      }

      setDmStreamingNarrativeBySession((prev) => {
        const previousContent = prev[sessionId] || '';
        const shouldAppend = typeof append === 'boolean'
          ? append
          : previousContent.length > 0;

        log.debug('updateStreamingNarrative | session=%s chunkLen=%d prevLen=%d append=%s final=%s',
          sessionId, content?.length || 0, previousContent.length, shouldAppend, isFinal);

        if (shouldAppend && content) {
          return { ...prev, [sessionId]: previousContent + content };
        }

        // If final chunk with empty content, preserve existing content
        if (isFinal && !content && previousContent) {
          return prev;
        }

        return { ...prev, [sessionId]: content };
      });

      setDmIsNarrativeStreamingBySession((prev) => ({
        ...prev,
        [sessionId]: isFinal ? false : isStreaming,
      }));
    },
    []
  );

  /**
   * Update streaming response content
   * Supports appending chunks or replacing content
   */
  const updateStreamingResponse = useCallback(
    (sessionId, content, { append, isStreaming = true, isFinal = false } = {}) => {
      if (!sessionId) {
        return;
      }

      setDmStreamingResponseBySession((prev) => {
        const previousContent = prev[sessionId] || '';
        const shouldAppend = typeof append === 'boolean'
          ? append
          : previousContent.length > 0;

        log.debug('updateStreamingResponse | session=%s chunkLen=%d prevLen=%d append=%s final=%s',
          sessionId, content?.length || 0, previousContent.length, shouldAppend, isFinal);

        if (shouldAppend && content) {
          return { ...prev, [sessionId]: previousContent + content };
        }

        // If final chunk with empty content, preserve existing content
        if (isFinal && !content && previousContent) {
          return prev;
        }

        return { ...prev, [sessionId]: content };
      });

      setDmIsResponseStreamingBySession((prev) => ({
        ...prev,
        [sessionId]: isFinal ? false : isStreaming,
      }));
    },
    []
  );

  /**
   * Clear streaming content for a session
   * Used when streaming completes or session switches
   */
  const clearStreaming = useCallback(
    (sessionId) => {
      if (!sessionId) {
        return;
      }

      setDmStreamingNarrativeBySession((prev) => {
        const updated = { ...prev };
        delete updated[sessionId];
        return updated;
      });

      setDmStreamingResponseBySession((prev) => {
        const updated = { ...prev };
        delete updated[sessionId];
        return updated;
      });

      setDmIsNarrativeStreamingBySession((prev) => ({
        ...prev,
        [sessionId]: false,
      }));

      setDmIsResponseStreamingBySession((prev) => ({
        ...prev,
        [sessionId]: false,
      }));
    },
    []
  );

  /**
   * Debug function to preview streaming state
   * Used for manual testing and debugging
   */
  const handleDebugStreamPreview = useCallback(
    (sessionId, narrative, playerResponse) => {
      if (!sessionId) {
        return;
      }

      if (typeof narrative === 'string') {
        setDmStreamingNarrativeBySession((prev) => ({
          ...prev,
          [sessionId]: narrative,
        }));
        if (narrative.trim()) {
          setDmIsNarrativeStreamingBySession((prev) => ({
            ...prev,
            [sessionId]: true,
          }));
          setTimeout(() => {
            setDmIsNarrativeStreamingBySession((prev) => {
              if (!prev[sessionId]) {
                return prev;
              }
              return {
                ...prev,
                [sessionId]: false,
              };
            });
          }, 1000);
        }
      }

      if (typeof playerResponse === 'string') {
        setDmStreamingResponseBySession((prev) => ({
          ...prev,
          [sessionId]: playerResponse,
        }));
        if (playerResponse.trim()) {
          setDmIsResponseStreamingBySession((prev) => ({
            ...prev,
            [sessionId]: true,
          }));
          setTimeout(() => {
            setDmIsResponseStreamingBySession((prev) => {
              if (!prev[sessionId]) {
                return prev;
              }
              return {
                ...prev,
                [sessionId]: false,
              };
            });
          }, 1000);
        }
      }
    },
    []
  );

  // Get streaming state for current campaign
  const streamingNarrative = currentCampaignId
    ? dmStreamingNarrativeBySession[currentCampaignId] || ''
    : '';
  const streamingResponse = currentCampaignId
    ? dmStreamingResponseBySession[currentCampaignId] || ''
    : '';
  const isNarrativeStreaming = currentCampaignId
    ? dmIsNarrativeStreamingBySession[currentCampaignId] || false
    : false;
  const isResponseStreaming = currentCampaignId
    ? dmIsResponseStreamingBySession[currentCampaignId] || false
    : false;

  return {
    // Current campaign state
    streamingNarrative,
    streamingResponse,
    isNarrativeStreaming,
    isResponseStreaming,

    // All sessions state (for legacy compatibility)
    allStreamingNarrative: dmStreamingNarrativeBySession,
    allStreamingResponse: dmStreamingResponseBySession,
    allIsNarrativeStreaming: dmIsNarrativeStreamingBySession,
    allIsResponseStreaming: dmIsResponseStreamingBySession,

    // Refs for callbacks
    isNarrativeStreamingRef: dmIsNarrativeStreamingRef,
    isResponseStreamingRef: dmIsResponseStreamingRef,

    // Operations
    updateStreamingNarrative,
    updateStreamingResponse,
    clearStreaming,
    handleDebugStreamPreview,

    // State setters (for direct access if needed)
    setStreamingNarrative: setDmStreamingNarrativeBySession,
    setStreamingResponse: setDmStreamingResponseBySession,
    setIsNarrativeStreaming: setDmIsNarrativeStreamingBySession,
    setIsResponseStreaming: setDmIsResponseStreamingBySession,
  };
}
