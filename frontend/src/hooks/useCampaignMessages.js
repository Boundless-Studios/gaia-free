import { useState, useCallback, useRef, useEffect } from 'react';
import apiService from '../services/apiService.js';
import { generateUniqueId } from '../utils/idGenerator.js';

// Monotonic counter to preserve insertion order across local and backend messages
let messageOrderCounter = 0;
const nextMessageOrder = () => {
  messageOrderCounter += 1;
  return messageOrderCounter;
};

/**
 * Merge local messages with backend history
 * Keeps local messages that aren't in backend yet, replaces with backend version when available
 */
function mergeMessages(localMessages, backendMessages, options = {}) {
  const { sessionId } = options;
  const merged = [];
  const backendByMessageId = new Map();
  const backendByTimestamp = new Map();
  const processedBackendIds = new Set();
  const dedupedEntries = [];
  const DEDUPE_TIME_WINDOW_MS = 5 * 60 * 1000; // 5 minutes

  const recordDeduplication = (entry) => {
    dedupedEntries.push(entry);
  };

  const normalizeTextForDedupe = (value) => {
    if (typeof value !== 'string') {
      return '';
    }
    return value.replace(/\s+/g, ' ').trim();
  };

  // Index backend messages by message_id and timestamp for fast lookup
  backendMessages.forEach(msg => {
    if (msg.message_id) {
      backendByMessageId.set(msg.message_id, msg);
    }
    if (msg.timestamp) {
      backendByTimestamp.set(msg.timestamp, msg);
    }
  });

  // Process local messages
  localMessages.forEach(localMsg => {
    let backendVersion = null;

    // Try to find backend version by message_id
    if (localMsg.message_id) {
      backendVersion = backendByMessageId.get(localMsg.message_id);
    }

    // Fallback: try to match by timestamp for older messages without message_id
    if (!backendVersion && localMsg.timestamp) {
      backendVersion = backendByTimestamp.get(localMsg.timestamp);
    }

    if (backendVersion) {
      const dedupeKey = backendVersion.message_id || backendVersion.timestamp || null;
      if (dedupeKey && processedBackendIds.has(dedupeKey)) {
        recordDeduplication({
          source: 'local',
          dedupeKey,
          messageId: backendVersion.message_id || null,
          timestamp: backendVersion.timestamp || null,
          localId: localMsg.id || null,
        });
        return;
      }

      // Preserve any local-only fields like character name
      const characterName = backendVersion.characterName || localMsg.characterName || null;
      const clientOrder = typeof localMsg.clientOrder === 'number'
        ? localMsg.clientOrder
        : (typeof backendVersion.clientOrder === 'number' ? backendVersion.clientOrder : nextMessageOrder());
      merged.push({
        ...backendVersion,
        characterName,
        isLocal: false,
        clientOrder,
      });
      if (dedupeKey) {
        processedBackendIds.add(dedupeKey);
      }
    } else if (localMsg.isLocal) {
      // Keep local message (not yet confirmed by backend)
      const clientOrder = typeof localMsg.clientOrder === 'number' ? localMsg.clientOrder : nextMessageOrder();
      merged.push({ ...localMsg, clientOrder });
    }
    // Skip local messages that are neither in backend nor marked isLocal
  });

  // Add any backend messages that weren't matched with local messages
  backendMessages.forEach(backendMsg => {
    const id = backendMsg.message_id || backendMsg.timestamp;
    if (!id || !processedBackendIds.has(id)) {
      const clientOrder = typeof backendMsg.clientOrder === 'number' ? backendMsg.clientOrder : nextMessageOrder();
      merged.push({ ...backendMsg, isLocal: false, clientOrder });
      if (id) {
        processedBackendIds.add(id);
      }
    } else {
      recordDeduplication({
        source: 'backend',
        dedupeKey: id,
        messageId: backendMsg.message_id || null,
        timestamp: backendMsg.timestamp || null,
      });
    }
  });

  if (dedupedEntries.length > 0) {
    console.warn(
      `[CHAT_DEBUG] mergeMessages deduped ${dedupedEntries.length} entr${dedupedEntries.length === 1 ? 'y' : 'ies'}${sessionId ? ` (session=${sessionId})` : ''}`,
      {
        deduplicated: dedupedEntries.slice(0, 5),
      }
    );
  }

  // Deduplicate provisional DM messages (missing message_id) once canonical copies arrive
  const provisionalDMByText = new Map();
  const dedupeLog = [];
  const mergedWithoutProvisionalDupes = [];

  merged.forEach((msg, index) => {
    if (!msg || msg.sender !== 'dm') {
      mergedWithoutProvisionalDupes.push(msg);
      return;
    }

    const textKey = `${msg.sender}|${normalizeTextForDedupe(msg.text) || ''}`;
    const hasMessageId = Boolean(msg.message_id);
    const existingIndex = provisionalDMByText.get(textKey);

    if (!hasMessageId && existingIndex == null) {
      provisionalDMByText.set(textKey, mergedWithoutProvisionalDupes.length);
      mergedWithoutProvisionalDupes.push(msg);
      return;
    }

    if (!hasMessageId && existingIndex != null) {
      const existing = mergedWithoutProvisionalDupes[existingIndex];
      const existingTime = existing?.timestamp ? new Date(existing.timestamp).getTime() : 0;
      const currentTime = msg.timestamp ? new Date(msg.timestamp).getTime() : 0;
      if (currentTime >= existingTime) {
        mergedWithoutProvisionalDupes[existingIndex] = msg;
      }
      return;
    }

    if (hasMessageId && existingIndex != null) {
      const existing = mergedWithoutProvisionalDupes[existingIndex];
      const existingTime = existing?.timestamp ? new Date(existing.timestamp).getTime() : 0;
      const currentTime = msg.timestamp ? new Date(msg.timestamp).getTime() : 0;
      const useCurrent = currentTime >= existingTime || !existing?.message_id;
      if (useCurrent) {
        mergedWithoutProvisionalDupes[existingIndex] = msg;
      }
      provisionalDMByText.delete(textKey);
      dedupeLog.push({
        textSample: textKey.slice(0, 120),
        replacedProvisional: Boolean(existing && !existing.message_id),
        existingTimestamp: existing?.timestamp || null,
        canonicalTimestamp: msg.timestamp || null,
        index,
      });
      return;
    }

    // Canonical DM message with unique text (or repeated with message_id) - keep as-is
    mergedWithoutProvisionalDupes.push(msg);
  });

  if (dedupeLog.length > 0) {
    console.warn(
      `[CHAT_DEBUG] Replaced ${dedupeLog.length} provisional DM message${dedupeLog.length === 1 ? '' : 's'} with canonical versions${sessionId ? ` (session=${sessionId})` : ''}`,
      {
        entries: dedupeLog.slice(0, 5),
      }
    );
  }

  // Sort by timestamp to ensure chronological order
  const dmByText = new Map();
  const dmDedupeLog = [];
  const finalMessages = [];

  const parseTime = (msg) => (msg?.timestamp ? new Date(msg.timestamp).getTime() : 0);

  mergedWithoutProvisionalDupes.forEach((msg) => {
    if (!msg || msg.sender !== 'dm') {
      finalMessages.push(msg);
      return;
    }

    const textKey = `${msg.sender}|${normalizeTextForDedupe(msg.text) || ''}`;
    const existingIndex = dmByText.get(textKey);
    const currentTime = parseTime(msg);

    if (existingIndex == null) {
      dmByText.set(textKey, finalMessages.length);
      finalMessages.push(msg);
      return;
    }

    const existing = finalMessages[existingIndex];
    const existingTime = parseTime(existing);
    const sameMessageId =
      msg.message_id && existing?.message_id && msg.message_id === existing.message_id;
    const timeClose = Math.abs(currentTime - existingTime) <= DEDUPE_TIME_WINDOW_MS;

    // Decide whether to replace existing with current
    const preferCurrent =
      sameMessageId ||
      (msg.message_id && !existing?.message_id) ||
      (timeClose && currentTime >= existingTime);

    if (preferCurrent) {
      finalMessages[existingIndex] = msg;
      dmDedupeLog.push({
        textSample: textKey.slice(0, 120),
        replacedIndex: existingIndex,
        existingMessageId: existing?.message_id || null,
        newMessageId: msg.message_id || null,
        existingTimestamp: existing?.timestamp || null,
        newTimestamp: msg.timestamp || null,
        reason: sameMessageId
          ? 'same_message_id'
          : msg.message_id && !existing?.message_id
            ? 'canonical_has_message_id'
            : 'newer_within_window',
      });
    } else {
      // Keep both messages if they are far apart; track the latest index for future dedupe
      dmByText.set(textKey, finalMessages.length);
      finalMessages.push(msg);
    }
  });

  if (dmDedupeLog.length > 0) {
    console.warn(
      `[CHAT_DEBUG] Collapsed ${dmDedupeLog.length} duplicate DM message${dmDedupeLog.length === 1 ? '' : 's'} by text${sessionId ? ` (session=${sessionId})` : ''}`,
      {
        entries: dmDedupeLog.slice(0, 5),
      }
    );
  }

  finalMessages.sort((a, b) => {
    const orderA = typeof a?.clientOrder === 'number' ? a.clientOrder : null;
    const orderB = typeof b?.clientOrder === 'number' ? b.clientOrder : null;
    if (orderA !== null && orderB !== null && orderA !== orderB) {
      return orderA - orderB;
    }
    const timeA = a?.timestamp ? new Date(a.timestamp).getTime() : 0;
    const timeB = b?.timestamp ? new Date(b.timestamp).getTime() : 0;
    if (timeA !== timeB) {
      return timeA - timeB;
    }
    return 0;
  });

  return finalMessages;
}

function logDuplicateMessages(sessionId, source, messages) {
  if (!Array.isArray(messages) || messages.length < 2) {
    return;
  }

  const duplicates = [];
  const trackDuplicates = (keyLabel, keyGetter) => {
    const seen = new Map();
    messages.forEach((msg, index) => {
      const key = keyGetter(msg);
      if (!key) {
        return;
      }
      if (seen.has(key)) {
        const firstIndex = seen.get(key);
        duplicates.push({
          keyType: keyLabel,
          key,
          firstIndex,
          secondIndex: index,
          firstSender: messages[firstIndex]?.sender || null,
          secondSender: msg?.sender || null,
          firstMessageId: messages[firstIndex]?.message_id || null,
          secondMessageId: msg?.message_id || null,
        });
      } else {
        seen.set(key, index);
      }
    });
  };

  trackDuplicates('message_id', (msg) => msg?.message_id);
  trackDuplicates('client_id', (msg) => msg?.id);

  if (!duplicates.length) {
    return;
  }

  console.warn(
    `[CHAT_DEBUG] Duplicate messages detected in session ${sessionId} (source=${source})`,
    {
      duplicates: duplicates.slice(0, 5),
      totalDuplicates: duplicates.length,
    }
  );
}

/**
 * Convert backend message format to frontend format
 * Handles different message structures from the API
 */
function convertBackendMessages(backendMessages) {
  if (!Array.isArray(backendMessages)) {
    return [];
  }

  return backendMessages.map((msg, index) => {
    let text = msg.content;
    let structuredContent = null;

    if (msg.role === 'assistant' && typeof msg.content === 'object') {
      structuredContent = {
        narrative: msg.content.narrative || null,
        answer: msg.content.answer || null,
      };
      text = msg.content.answer || msg.content.narrative || JSON.stringify(msg.content);
    } else if (typeof msg.content !== 'string') {
      text = JSON.stringify(msg.content);
    }

    const metadata = msg.metadata || {};
    const content = typeof msg.content === 'object' && msg.content ? msg.content : {};

    const metadataCharacter =
      msg.character_name ||
      msg.characterName ||
      metadata.character_name ||
      metadata.characterName ||
      metadata.player_name ||
      metadata.playerName ||
      metadata.character?.display_name ||
      metadata.character?.name ||
      metadata.turn_info?.character_name ||
      metadata.turn_info?.characterName ||
      content.character_name ||
      content.characterName ||
      content.metadata?.character_name ||
      content.metadata?.characterName ||
      content.metadata?.character?.display_name ||
      content.metadata?.character?.name ||
      content.turn_info?.character_name ||
      content.turn_info?.characterName ||
      null;

    return {
      id: generateUniqueId(),
      message_id: msg.message_id,
      text,
      structuredContent,
      sender: msg.role === 'assistant' ? 'dm' : msg.role,
      timestamp: msg.timestamp || new Date().toISOString(),
      isLocal: false,
      characterName: metadataCharacter || null,
      clientOrder: nextMessageOrder(),
    };
  });
}

/**
 * Custom hook to manage campaign messages per session
 * Handles message state, creation, merging, normalization, and audio flags
 *
 * @param {string} currentCampaignId - The active campaign ID
 * @param {Object} streamingState - Streaming state setters from useStreamingState
 * @returns {Object} Message management interface
 */
export function useCampaignMessages(currentCampaignId, streamingState = {}) {
  const [messagesBySession, setMessagesBySession] = useState({});
  const messagesBySessionRef = useRef(messagesBySession);

  // Keep ref in sync with state
  useEffect(() => {
    messagesBySessionRef.current = messagesBySession;
  }, [messagesBySession]);

  /**
   * Set messages for a specific session
   * Supports both direct values and updater functions
   */
  const setSessionMessages = useCallback(
    (sessionId, updater) => {
      if (!sessionId) {
        return;
      }
      setMessagesBySession((previous) => {
        const current = previous[sessionId] || [];
        const next = typeof updater === 'function' ? updater(current) : updater;
        if (next === current) {
          return previous;
        }
        if (Array.isArray(next)) {
          logDuplicateMessages(sessionId, 'setSessionMessages', next);
        }
        const updated = { ...previous, [sessionId]: next };
        messagesBySessionRef.current = updated;
        return updated;
      });
    },
    []
  );

  /**
   * Normalize message text by collapsing whitespace
   */
  const normalizeMessageText = useCallback((value) => {
    if (typeof value !== 'string') {
      return value;
    }
    return value.replace(/\s+/g, ' ').trim();
  }, []);

  /**
   * Mark the last DM message in a session as having audio
   * Used when audio playback starts for a message
   */
  const markLastDmMessageHasAudio = useCallback(
    (sessionId) => {
      if (!sessionId) {
        return;
      }
      setSessionMessages(sessionId, (previous) => {
        if (!previous.length) {
          return previous;
        }
        // Find the last DM message
        for (let index = previous.length - 1; index >= 0; index -= 1) {
          const candidate = previous[index];
          if (candidate?.sender === 'dm') {
            // If already marked, no update needed
            if (candidate.hasAudio) {
              return previous;
            }
            // Mark this message as having audio
            const updated = [...previous];
            updated[index] = { ...candidate, hasAudio: true };
            return updated;
          }
        }
        return previous;
      });
    },
    [setSessionMessages]
  );

  /**
   * Merge local messages with backend messages
   * Replaces local messages with confirmed backend versions
   *
   * @param {string} sessionId - The session to update
   * @param {Array} backendMessages - Messages from the backend
   */
  const mergeWithBackend = useCallback(
    (sessionId, backendMessages) => {
      if (!sessionId || !backendMessages) {
        return;
      }
      setSessionMessages(sessionId, (localMessages) => {
        const merged = mergeMessages(localMessages, backendMessages, { sessionId });
        console.log('🔄 Merged messages:', merged.length, '(', localMessages.length, 'local +', backendMessages.length, 'backend)');
        logDuplicateMessages(sessionId, 'mergeWithBackend', merged);
        return merged;
      });
    },
    [setSessionMessages]
  );

  /**
   * Add a user message to the session
   *
   * @param {string} sessionId - The session to add to
   * @param {string} text - The message text
   * @param {Object} options - Additional message options (messageId, characterName, etc.)
   */
  const addUserMessage = useCallback(
    (sessionId, text, options = {}) => {
      if (!sessionId || !text) {
        return;
      }

      const userMessage = {
        id: generateUniqueId(),
        message_id: options.messageId || `msg_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`,
        text,
        sender: 'user',
        timestamp: options.timestamp || new Date().toISOString(),
        characterName: options.characterName,
        isLocal: true,
        isContext: options.isContext || false,
        clientOrder: nextMessageOrder(),
      };

      setSessionMessages(sessionId, (prev) => [...prev, userMessage]);
      return userMessage;
    },
    [setSessionMessages]
  );

  /**
   * Add a context message to the session
   *
   * @param {string} sessionId - The session to add to
   * @param {string} contextText - The context text
   */
  const addContextMessage = useCallback(
    (sessionId, contextText) => {
      return addUserMessage(sessionId, `[CONTEXT] ${contextText}`, { isContext: true });
    },
    [addUserMessage]
  );

  /**
   * Add a DM message with duplicate detection
   *
   * @param {string} sessionId - The session to add to
   * @param {string} text - The message text
   * @param {Object} options - Message options (structuredContent, hasAudio, etc.)
   * @returns {boolean} - Whether the message was added (false if duplicate)
   */
  const addDMMessage = useCallback(
    (sessionId, text, options = {}) => {
      if (!sessionId || !text) {
        return false;
      }

      const timestamp = options.timestamp || new Date().toISOString();
      const normalizedAnswer = normalizeMessageText(text);
      let messageAdded = false;

      setSessionMessages(sessionId, (prev) => {
        // Check for duplicates
        const hasDuplicate = prev.some((msg) => {
          if (msg.sender !== 'dm') {
            return false;
          }
          const candidateText = normalizeMessageText(msg.text);
          if (candidateText !== normalizedAnswer) {
            return false;
          }
          if (!msg.timestamp) {
            return false;
          }
          return new Date(msg.timestamp).getTime() === new Date(timestamp).getTime();
        });

        if (hasDuplicate) {
          return prev;
        }

        messageAdded = true;
        const dmMessage = {
          id: generateUniqueId(),
          text,
          sender: 'dm',
          timestamp,
          hasAudio: Boolean(options.hasAudio),
          structuredContent: options.structuredContent || null,
          isStreamed: Boolean(options.isStreamed),
          clientOrder: nextMessageOrder(),
        };
        return [...prev, dmMessage];
      });

      return messageAdded;
    },
    [setSessionMessages, normalizeMessageText]
  );

  /**
   * Add a system error message to the session
   *
   * @param {string} sessionId - The session to add to
   * @param {string} errorText - The error message
   */
  const addSystemError = useCallback(
    (sessionId, errorText) => {
      if (!sessionId || !errorText) {
        return;
      }

      const errorMessage = {
        id: generateUniqueId(),
        text: `Error: ${errorText}`,
        sender: 'system',
        timestamp: new Date().toISOString(),
        clientOrder: nextMessageOrder(),
      };

      setSessionMessages(sessionId, (prev) => [...prev, errorMessage]);
    },
    [setSessionMessages]
  );

  /**
   * Reload chat history from backend after streaming response
   * Merges backend messages and clears streaming state
   *
   * @param {string} sessionId - The session to reload
   */
  const reloadHistoryAfterStream = useCallback(
    async (sessionId) => {
      if (!sessionId) {
        return;
      }

      console.log('🔄 Reloading chat history after streamed response');

      try {
        const campaignData = await apiService.loadSimpleCampaign(sessionId);

        if (campaignData?.messages) {
          // Convert backend messages to frontend format
          const backendMessages = convertBackendMessages(campaignData.messages);

          // Merge local messages with backend history
          mergeWithBackend(sessionId, backendMessages);

          // Clear streaming state after history has loaded
          if (streamingState.clearNarrativeStreaming) {
            streamingState.clearNarrativeStreaming(sessionId);
          }
          if (streamingState.clearResponseStreaming) {
            streamingState.clearResponseStreaming(sessionId);
          }
        }
      } catch (error) {
        console.error('Failed to reload chat history:', error);

        // On error, still clear streaming state
        if (streamingState.clearNarrativeStreaming) {
          streamingState.clearNarrativeStreaming(sessionId);
        }
        if (streamingState.clearResponseStreaming) {
          streamingState.clearResponseStreaming(sessionId);
        }
      }
    },
    [mergeWithBackend, streamingState]
  );

  // Get messages for current campaign
  const messages = currentCampaignId ? messagesBySession[currentCampaignId] || [] : [];

  return {
    // State
    messages,                      // Messages for current campaign
    allMessages: messagesBySession, // All messages by session (for legacy compatibility)
    messagesRef: messagesBySessionRef,

    // Operations
    setMessages: setSessionMessages,
    normalizeMessageText,
    markLastDmMessageHasAudio,
    mergeWithBackend,

    // Message creation
    addUserMessage,
    addContextMessage,
    addDMMessage,
    addSystemError,

    // History management
    reloadHistoryAfterStream,
    convertBackendMessages,
  };
}
