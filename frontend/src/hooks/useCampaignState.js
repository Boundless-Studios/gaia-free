import { useState, useCallback } from 'react';
import apiService from '../services/apiService.js';
import { loggers } from '../utils/logger.js';

const log = loggers.campaign;

/**
 * Transform structured data from backend into normalized frontend format
 * @param {Object} structuredData - Raw structured data from backend
 * @param {Object} options - Transformation options
 * @returns {Object|null} Transformed structured data
 */
function transformStructuredData(structuredData, { needsResponse = false, sessionId = null } = {}) {
  if (!structuredData || typeof structuredData !== 'object') {
    return null;
  }

  const parseField = (value) => (value ? apiService.parseField(value) : value);
  const narrative = structuredData.narrative || structuredData.answer || '';
  const streamingAnswer = structuredData.streaming_answer || structuredData.streamingAnswer || '';
  const streamingToolEvents = parseField(
    structuredData.streaming_tool_events || structuredData.streamingToolEvents
  ) || [];
  const observations = parseField(structuredData.observations) || [];
  const summary = structuredData.summary || '';
  const personalizedPlayerOptions = parseField(structuredData.personalized_player_options) || null;
  const pendingObservations = parseField(structuredData.pending_observations) || null;
  const rawPlayerOptions =
    structuredData.player_options ??
    structuredData.turn ??
    structuredData.player_response ??
    null;

  const transformed = {
    narrative,
    turn: structuredData.turn || '',
    player_options: parseField(rawPlayerOptions) || '',
    characters: parseField(structuredData.characters) || '',
    status: parseField(structuredData.status) || '',
    environmental_conditions: structuredData.environmental_conditions || '',
    immediate_threats: structuredData.immediate_threats || '',
    story_progression: structuredData.story_progression || '',
    answer: structuredData.answer || narrative,
    summary,
    observations,
    streaming_answer: streamingAnswer,
    streaming_tool_events: streamingToolEvents,
    streamed: Boolean(structuredData.streamed),
    input_needed: needsResponse || Boolean(structuredData.input_needed),
    turn_info: parseField(structuredData.turn_info) || null,
    combat_status: parseField(structuredData.combat_status) || null,
    combat_state: structuredData.combat_state || null,
    action_breakdown: parseField(structuredData.action_breakdown) || null,
    turn_resolution: parseField(structuredData.turn_resolution) || null,
    generated_image_url: structuredData.generated_image_url || '',
    generated_image_path: structuredData.generated_image_path || '',
    generated_image_prompt: structuredData.generated_image_prompt || '',
    generated_image_type: structuredData.generated_image_type || '',
    original_data: structuredData,
    perception_checks:
      parseField(structuredData.metadata?.perception_checks) ||
      parseField(structuredData.perception_checks) ||
      observations,
    personalized_player_options: personalizedPlayerOptions,
    pending_observations: pendingObservations,
  };

  if (structuredData.audio) {
    const audioPayload = apiService.mapAudioPayload(structuredData.audio, sessionId);
    if (audioPayload?.url) {
      transformed.audio = audioPayload;
    }
  }

  return transformed;
}

/**
 * Custom hook to manage campaign-scoped state
 * Handles structured data, history info, resume state, player suggestions, etc.
 *
 * @param {string} currentCampaignId - The active campaign ID
 * @returns {Object} Campaign state management interface
 */
export function useCampaignState(currentCampaignId) {
  const [structuredDataBySession, setStructuredDataBySession] = useState({});
  const [historyInfoBySession, setHistoryInfoBySession] = useState({});
  const [needsResumeBySession, setNeedsResumeBySession] = useState({});
  const [pendingInitialNarrativeBySession, setPendingInitialNarrativeBySession] = useState({});

  /**
   * Set structured data for a specific session
   */
  const setSessionStructuredData = useCallback(
    (sessionId, updater) => {
      if (!sessionId) {
        return;
      }
      setStructuredDataBySession((previous) => {
        const current = Object.prototype.hasOwnProperty.call(previous, sessionId)
          ? previous[sessionId]
          : null;
        const next = typeof updater === 'function' ? updater(current) : updater;
        if (next === current) {
          return previous;
        }
        log.debug('setSessionStructuredData | session=%s hasNarrative=%s', sessionId, Boolean(next?.narrative || next?.answer));
        return { ...previous, [sessionId]: next };
      });
    },
    []
  );

  /**
   * Set history info for a specific session
   */
  const setSessionHistoryInfo = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setHistoryInfoBySession((previous) => {
        if (previous[sessionId] === value) {
          return previous;
        }
        return { ...previous, [sessionId]: value };
      });
    },
    []
  );

  /**
   * Set needs resume flag for a specific session
   */
  const setSessionNeedsResume = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setNeedsResumeBySession((previous) => {
        const normalized = Boolean(value);
        if (previous[sessionId] === normalized) {
          return previous;
        }
        return { ...previous, [sessionId]: normalized };
      });
    },
    []
  );

  /**
   * Set pending initial narrative flag for a specific session
   */
  const setPendingInitialNarrative = useCallback(
    (sessionId, value) => {
      if (!sessionId) {
        return;
      }
      setPendingInitialNarrativeBySession((previous) => {
        const normalized = Boolean(value);
        const current = Boolean(previous[sessionId]);
        if (normalized === current) {
          return previous;
        }
        if (!normalized) {
          const next = { ...previous };
          delete next[sessionId];
          return next;
        }
        return { ...previous, [sessionId]: true };
      });
    },
    []
  );


  // Derived state for current campaign
  const structuredData = currentCampaignId
    ? structuredDataBySession[currentCampaignId] ?? null
    : null;
  const historyInfo = currentCampaignId
    ? historyInfoBySession[currentCampaignId] ?? null
    : null;
  const needsResume = currentCampaignId
    ? needsResumeBySession[currentCampaignId] ?? false
    : false;
  const pendingInitialNarrative = currentCampaignId
    ? Boolean(pendingInitialNarrativeBySession[currentCampaignId])
    : false;

  return {
    // Current campaign state
    structuredData,
    historyInfo,
    needsResume,
    pendingInitialNarrative,

    // All sessions state (for legacy compatibility)
    allStructuredData: structuredDataBySession,
    allHistoryInfo: historyInfoBySession,
    allNeedsResume: needsResumeBySession,
    allPendingInitialNarrative: pendingInitialNarrativeBySession,

    // Setters
    setStructuredData: setSessionStructuredData,
    setHistoryInfo: setSessionHistoryInfo,
    setNeedsResume: setSessionNeedsResume,
    setPendingInitialNarrative,

    // Utility
    transformStructuredData,
  };
}
