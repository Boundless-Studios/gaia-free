/**
 * RoomContext - Centralized state management for game room/seat system
 * Handles room state, WebSocket events, and seat operations
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import apiService from '../services/apiService.js';

const CAMPAIGN_START_TRACE = '[CAMPAIGN_START_FLOW]';

const RoomContext = createContext(null);

/**
 * RoomProvider component
 * @param {Object} props
 * @param {string} props.campaignId - Campaign/session ID
 * @param {string} [props.currentUserId] - Authenticated user ID (used for auto DM claim)
 * @param {{name?: string|null, email?: string|null}} [props.currentUserProfile] - Current user profile for display fallbacks
 * @param {Object} [props.webSocketRef] - WebSocket reference (legacy, optional if using Socket.IO)
 * @param {Object} [props.socketRef] - Socket.IO socket reference (optional, preferred over webSocketRef)
 * @param {Function} props.onRoomEvent - Optional callback for room events
 * @param {React.ReactNode} props.children
 */
export const RoomProvider = ({
  campaignId,
  currentUserId,
  currentUserProfile = null,
  webSocketRef,
  socketRef,
  webSocketVersion = 0,
  onRoomEvent,
  children,
}) => {
  const [roomState, setRoomState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoClaimError, setAutoClaimError] = useState(null);
  const [autoClaimingDMSeat, setAutoClaimingDMSeat] = useState(false);
  const lastAutoClaimAttemptRef = useRef(0);
  const [tokenProviderReady, setTokenProviderReady] = useState(Boolean(apiService.getAccessToken));

  useEffect(() => {
    const unsubscribe = apiService.subscribeTokenProvider(() => {
      setTokenProviderReady(true);
    });
    return unsubscribe;
  }, []);

  // Fetch initial room state
  const fetchRoomState = useCallback(async () => {
    if (!campaignId || !tokenProviderReady) {
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const [stateResult, summaryResult] = await Promise.all([
        apiService.getRoomState(campaignId),
        apiService.getRoomSummary(campaignId),
      ]);
      console.debug('[RoomContext] Initial room state fetched', {
        state: stateResult,
        summary: summaryResult,
      });
      const merged = {
        ...stateResult,
        owner_user_id: stateResult.owner_user_id ?? summaryResult?.owner_user_id ?? null,
        owner_email: stateResult.owner_email ?? summaryResult?.owner_email ?? null,
        owner_identity: stateResult.owner_identity ?? summaryResult?.owner_identity ?? null,
        invited_players: summaryResult?.invited_players ?? stateResult.invited_players ?? [],
        room_summary: summaryResult || null,
      };
      setRoomState(merged);
    } catch (err) {
      console.error('Failed to fetch room state:', err);
      setError(err.message || 'Failed to load room state');
    } finally {
      setLoading(false);
    }
  }, [campaignId, tokenProviderReady]);

  // Initial fetch
  useEffect(() => {
    fetchRoomState();
  }, [fetchRoomState]);

  const applySeatUpdate = useCallback((updatedSeat) => {
    if (!updatedSeat?.seat_id) {
      console.warn('[RoomContext] applySeatUpdate missing seat_id', updatedSeat);
      return;
    }
    console.debug('[RoomContext] applySeatUpdate ->', updatedSeat);
    setRoomState(prev => {
      if (!prev || !prev.seats) return prev;

      let didUpdate = false;
      const updatedSeats = prev.seats.map(seat => {
        if (seat.seat_id === updatedSeat.seat_id) {
          didUpdate = true;
          return { ...seat, ...updatedSeat };
        }
        return seat;
      });

      if (!didUpdate) {
        console.warn('Seat update mismatch - seat not found, refetching full state');
        fetchRoomState();
        return prev;
      }

      const nextState = {
        ...prev,
        seats: updatedSeats
      };

      const targetSeat = updatedSeats.find(seat => seat.seat_id === updatedSeat.seat_id);
      if (targetSeat?.seat_type === 'dm') {
        const newOwner = targetSeat.owner_user_id ?? null;
        const newOwnerIdentity =
          updatedSeat.owner_identity ??
          targetSeat.owner_identity ??
          nextState.owner_identity ??
          null;
        if (newOwner !== nextState.owner_user_id) {
          console.debug('[RoomContext] DM seat owner change detected', {
            previousOwner: nextState.owner_user_id,
            newOwner,
          });
        }
        nextState.owner_user_id = newOwner ?? nextState.owner_user_id ?? null;
        nextState.owner_identity = newOwnerIdentity ?? nextState.owner_identity ?? null;
      }

      return nextState;
    });
  }, [fetchRoomState]);

  // WebSocket event: seat updated
  const handleSeatUpdate = useCallback((updatedSeat) => {
    console.log('🪑 Room: Seat updated', updatedSeat);
    applySeatUpdate(updatedSeat);
    onRoomEvent?.({ type: 'seat_updated', data: updatedSeat });
  }, [applySeatUpdate, onRoomEvent]);

  // WebSocket event: DM joined
  const handleDMJoined = useCallback((data) => {
    console.log('🎭 Room: DM joined', data);
    const dmUserId = data.dm_user_id || data.user_id || null;
    setRoomState(prev => {
      if (!prev || !prev.seats) return prev;

      return {
        ...prev,
        room_status: data.room_status || 'active',
        dm_joined_at: data.dm_joined_at || new Date().toISOString(),
        seats: prev.seats.map(seat =>
          seat.seat_type === 'dm'
            ? {
                ...seat,
                owner_user_id: dmUserId ?? seat.owner_user_id,
                online: true,
                status: 'occupied',
              }
            : seat
        )
      };
    });

    onRoomEvent?.({ type: 'dm_joined', data: { ...data, dm_user_id: dmUserId } });
  }, [onRoomEvent]);

  // WebSocket event: DM left
  const handleDMLeft = useCallback((data) => {
    console.log('🎭 Room: DM left', data);

    setRoomState(prev => {
      if (!prev || !prev.seats) return prev;

      return {
        ...prev,
        room_status: 'waiting_for_dm',
        dm_joined_at: null,
        seats: prev.seats.map(seat =>
          seat.seat_type === 'dm'
            ? { ...seat, online: false }
            : seat
        )
      };
    });

    onRoomEvent?.({ type: 'dm_left', data });
  }, [onRoomEvent]);

  // WebSocket event: player vacated
  const handlePlayerVacated = useCallback((data) => {
    console.log('🪑 Room: Player vacated', data);

    const { seat_id, previous_owner } = data;

    // Update seat state
    setRoomState(prev => {
      if (!prev || !prev.seats) return prev;

      return {
        ...prev,
        seats: prev.seats.map(seat =>
          seat.seat_id === seat_id
            ? { ...seat, owner_user_id: null, online: false }
            : seat
        )
      };
    });

    onRoomEvent?.({ type: 'player_vacated', data: { seat_id, previous_owner } });
  }, [onRoomEvent]);

  // WebSocket event: campaign started
  const handleCampaignStarted = useCallback((data) => {
    console.log('🚀 Room: Campaign started', data);
    if (data?.campaign_id) {
      console.debug(
        `${CAMPAIGN_START_TRACE} RoomContext received room.campaign_started`,
        {
          sessionId: data.campaign_id,
          payloadKeys: Object.keys(data || {}),
        },
      );
    }

    setRoomState(prev => ({
      ...prev,
      campaign_status: 'active',
      started_at: data.started_at || new Date().toISOString()
    }));

    console.debug(
      `${CAMPAIGN_START_TRACE} RoomContext dispatching campaign_started`,
      {
        sessionId: data?.campaign_id || null,
      },
    );
    onRoomEvent?.({ type: 'campaign_started', data });
  }, [onRoomEvent]);

  // Subscribe to Socket.IO events (preferred)
  useEffect(() => {
    const socket = socketRef?.current;
    if (!socket) return;

    // Socket.IO event handlers
    const onSeatUpdated = (data) => handleSeatUpdate(data.seat || data);
    const onDMJoined = (data) => handleDMJoined(data);
    const onDMLeft = (data) => handleDMLeft(data);
    const onPlayerVacated = (data) => handlePlayerVacated(data);
    const onCampaignStarted = (data) => handleCampaignStarted(data);

    socket.on('room.seat_updated', onSeatUpdated);
    socket.on('room.dm_joined', onDMJoined);
    socket.on('room.dm_left', onDMLeft);
    socket.on('room.player_vacated', onPlayerVacated);
    socket.on('room.campaign_started', onCampaignStarted);

    // Refresh room state when socket becomes available
    // This catches any events that fired before we subscribed (e.g., room.dm_joined on connect)
    if (socket.connected) {
      console.debug('[RoomContext] Socket connected, refreshing room state');
      fetchRoomState();
    }

    return () => {
      socket.off('room.seat_updated', onSeatUpdated);
      socket.off('room.dm_joined', onDMJoined);
      socket.off('room.dm_left', onDMLeft);
      socket.off('room.player_vacated', onPlayerVacated);
      socket.off('room.campaign_started', onCampaignStarted);
    };
  }, [
    socketRef,
    handleSeatUpdate,
    handleDMJoined,
    handleDMLeft,
    handlePlayerVacated,
    handleCampaignStarted,
    fetchRoomState
  ]);

  // Subscribe to WebSocket events (legacy fallback)
  useEffect(() => {
    // Skip if using Socket.IO
    if (socketRef?.current) return;

    const ws = webSocketRef?.current;
    if (!ws) return;

    // Add room event listeners
    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Route room events to handlers
        switch (data.type) {
          case 'room.seat_updated':
            handleSeatUpdate(data.seat || data);
            break;
          case 'room.dm_joined':
            handleDMJoined(data);
            break;
          case 'room.dm_left':
            handleDMLeft(data);
            break;
          case 'room.player_vacated':
            handlePlayerVacated(data);
            break;
          case 'room.campaign_started':
            handleCampaignStarted(data);
            break;
          default:
            // Ignore non-room events (handled by other systems)
            break;
        }
      } catch (err) {
        console.error('Room: Error parsing WebSocket message', err);
      }
    };

    ws.addEventListener('message', handleMessage);

    return () => {
      ws.removeEventListener('message', handleMessage);
    };
  }, [
    socketRef,
    webSocketRef,
    webSocketVersion,
    handleSeatUpdate,
    handleDMJoined,
    handleDMLeft,
    handlePlayerVacated,
    handleCampaignStarted
  ]);

  // API methods
  const occupySeat = useCallback(async (seatId) => {
    try {
      const seat = await apiService.occupySeat(campaignId, seatId);
      if (seat) {
        console.debug('[RoomContext] Occupy seat API response', seat);
        applySeatUpdate(seat);
      }
      return seat;
    } catch (err) {
      console.error('Failed to occupy seat:', err);
      throw err;
    }
  }, [campaignId, applySeatUpdate]);

  const releaseSeat = useCallback(async (seatId) => {
    try {
      const seat = await apiService.releaseSeat(campaignId, seatId);
      if (seat) {
        console.debug('[RoomContext] Release seat API response', seat);
        applySeatUpdate(seat);
      }
    } catch (err) {
      console.error('Failed to release seat:', err);
      throw err;
    }
  }, [campaignId, applySeatUpdate]);

  const vacateSeat = useCallback(async (seatId, notifyUser = true) => {
    try {
      const seat = await apiService.vacateSeat(campaignId, seatId, { notify_user: notifyUser });
      if (seat?.seat) {
        console.debug('[RoomContext] Vacate seat API response', seat);
        applySeatUpdate({ ...seat.seat });
      } else if (seat) {
        console.debug('[RoomContext] Vacate seat API response (legacy)', seat);
        applySeatUpdate(seat);
      }
    } catch (err) {
      console.error('Failed to vacate seat:', err);
      throw err;
    }
  }, [campaignId, applySeatUpdate]);

  const assignCharacter = useCallback(async (seatId, characterData) => {
    try {
      const result = await apiService.assignCharacterToSeat(campaignId, seatId, characterData);
      // State updated via WebSocket event
      return result;
    } catch (err) {
      console.error('Failed to assign character:', err);
      throw err;
    }
  }, [campaignId]);

  const startCampaign = useCallback(async () => {
    try {
      const result = await apiService.startCampaign(campaignId);
      // State updated via WebSocket event
      return result;
    } catch (err) {
      console.error('Failed to start campaign:', err);
      throw err;
    }
  }, [campaignId]);

  // Derived getters (using useMemo for performance)
  const normalizedRoomState = useMemo(() => {
    if (!roomState || !roomState.seats?.length) {
      return roomState;
    }
    const dmSeatRaw = roomState.seats.find(s => s.seat_type === 'dm');
    if (!dmSeatRaw) return roomState;
    const resolvedOwnerIdentity =
      roomState.owner_identity ||
      dmSeatRaw.owner_identity ||
      null;
    const ownerDisplay =
      dmSeatRaw.owner_display_name ||
      roomState.owner_display_name ||
      currentUserProfile?.name ||
      currentUserProfile?.email ||
      dmSeatRaw.owner_email ||
      roomState.owner_email ||
      null;
    const ownerEmail =
      dmSeatRaw.owner_email ||
      roomState.owner_email ||
      currentUserProfile?.email ||
      null;
    if (dmSeatRaw.owner_user_id || !roomState.owner_user_id) {
      if (!roomState.owner_identity && resolvedOwnerIdentity) {
        return {
          ...roomState,
          owner_identity: resolvedOwnerIdentity,
        };
      }
      return roomState;
    }
    const patchedSeats = roomState.seats.map(seat =>
      seat.seat_type === 'dm'
        ? {
            ...seat,
            owner_user_id: roomState.owner_user_id,
            owner_display_name: ownerDisplay,
            owner_email: ownerEmail,
            status: seat.status === 'available' ? 'occupied' : seat.status,
            owner_identity: resolvedOwnerIdentity || seat.owner_identity || null,
          }
        : seat
    );
    return {
      ...roomState,
      owner_display_name: ownerDisplay ?? roomState.owner_display_name,
      owner_email: ownerEmail ?? roomState.owner_email,
      owner_identity: resolvedOwnerIdentity || roomState.owner_identity || null,
      seats: patchedSeats,
    };
  }, [roomState, currentUserProfile]);

  const playerSeats = useMemo(() => {
    return normalizedRoomState?.seats?.filter(s => s.seat_type === 'player') || [];
  }, [normalizedRoomState?.seats]);

  const dmSeat = useMemo(() => {
    return normalizedRoomState?.seats?.find(s => s.seat_type === 'dm') || null;
  }, [normalizedRoomState?.seats]);

  const currentUserSeat = useMemo(() => {
    if (!currentUserId || !normalizedRoomState?.seats?.length) {
      return null;
    }
    return (
      normalizedRoomState.seats.find((seat) => {
        const ownerId =
          seat.owner_identity?.gaia_user_id ||
          seat.owner_user_id ||
          null;
        return ownerId === currentUserId;
      }) || null
    );
  }, [currentUserId, normalizedRoomState?.seats]);

  const currentUserSeatNeedsCharacter = useMemo(() => {
    if (!currentUserSeat) return false;
    return !currentUserSeat.character_id;
  }, [currentUserSeat]);

  const currentUserPlayerSeat = useMemo(() => {
    if (!currentUserId || !normalizedRoomState?.seats?.length) {
      return null;
    }
    return (
      normalizedRoomState.seats.find((seat) => {
        if (seat.seat_type !== 'player') {
          return false;
        }
        const ownerId =
          seat.owner_identity?.gaia_user_id ||
          seat.owner_user_id ||
          null;
        return ownerId === currentUserId;
      }) || null
    );
  }, [currentUserId, normalizedRoomState?.seats]);

  const currentUserPlayerSeatNeedsCharacter = useMemo(() => {
    if (!currentUserPlayerSeat) return false;
    return !currentUserPlayerSeat.character_id;
  }, [currentUserPlayerSeat]);

  const dmSeatOwnerId = useMemo(() => {
    if (!dmSeat) return null;
    return dmSeat.owner_identity?.gaia_user_id ?? dmSeat.owner_user_id ?? null;
  }, [dmSeat]);

  const normalizedOwnerId = useMemo(() => {
    if (!normalizedRoomState) return null;
    return normalizedRoomState.owner_identity?.gaia_user_id ?? normalizedRoomState.owner_user_id ?? null;
  }, [normalizedRoomState]);

  const isDMSeated = useMemo(() => {
    return dmSeatOwnerId !== null;
  }, [dmSeatOwnerId]);
  const currentUserIsOwner = useMemo(() => {
    return Boolean(currentUserId && normalizedOwnerId === currentUserId);
  }, [currentUserId, normalizedOwnerId]);

  const shouldAutoClaimDMSeat = useMemo(() => {
    if (!campaignId || !currentUserId || !normalizedRoomState || !dmSeat) return false;
    if (normalizedOwnerId && normalizedOwnerId !== currentUserId) return false;
    if (dmSeatOwnerId && dmSeatOwnerId !== currentUserId) return false;
    return dmSeatOwnerId !== currentUserId;
  }, [campaignId, currentUserId, normalizedRoomState, dmSeat, normalizedOwnerId, dmSeatOwnerId]);

  useEffect(() => {
    setAutoClaimError(null);
    lastAutoClaimAttemptRef.current = 0;
  }, [campaignId, currentUserId]);

  // Automatically occupy DM seat for the campaign owner
  useEffect(() => {
    if (!shouldAutoClaimDMSeat || !dmSeat) {
      return undefined;
    }

    const now = Date.now();
    if (now - lastAutoClaimAttemptRef.current < 2000) {
      return undefined;
    }
    lastAutoClaimAttemptRef.current = now;

    let cancelled = false;
    setAutoClaimingDMSeat(true);
    setAutoClaimError(null);

    occupySeat(dmSeat.seat_id)
      .catch((err) => {
        if (!cancelled) {
          console.error('Auto-claim DM seat failed:', err);
          setAutoClaimError(err.message || 'Failed to auto-claim DM seat');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAutoClaimingDMSeat(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [shouldAutoClaimDMSeat, dmSeat, occupySeat]);

  const canStartCampaign = useMemo(() => {
    if (!isDMSeated) return false;
    if (normalizedRoomState?.campaign_status === 'active') return false;
    if (normalizedRoomState?.room_status !== 'active') return false;
    const seatsWithCharacters = playerSeats.filter(s => s.character_id !== null);
    return seatsWithCharacters.length > 0;
  }, [isDMSeated, playerSeats, normalizedRoomState?.campaign_status, normalizedRoomState?.room_status]);

  const filledSeats = useMemo(() => {
    return normalizedRoomState?.seats?.filter(s => s.owner_user_id !== null).length || 0;
  }, [normalizedRoomState?.seats]);

  const seatsWithCharacters = useMemo(() => {
    return normalizedRoomState?.seats?.filter(s => s.character_id !== null).length || 0;
  }, [normalizedRoomState?.seats]);

  const value = {
    campaignId,
    // State
    roomState: normalizedRoomState,
    roomSummary: normalizedRoomState?.room_summary || null,
    loading,
    error,

    // API methods
    occupySeat,
    releaseSeat,
    vacateSeat,
    assignCharacter,
    startCampaign,
    refreshRoomState: fetchRoomState,

    // Derived getters
    playerSeats,
    dmSeat,
    isDMSeated,
    currentUserIsOwner,
    canStartCampaign,
    filledSeats,
    seatsWithCharacters,
    currentUserSeat,
    currentUserSeatNeedsCharacter,
    currentUserPlayerSeat,
    currentUserPlayerSeatNeedsCharacter,
    autoClaimingDMSeat,
    autoClaimError,
    shouldAutoClaimDMSeat,
  };

  return <RoomContext.Provider value={value}>{children}</RoomContext.Provider>;
};

/**
 * Hook to use room context
 * @returns {Object} Room context value
 */
export const useRoom = () => {
  const context = useContext(RoomContext);
  if (!context) {
    throw new Error('useRoom must be used within RoomProvider');
  }
  return context;
};

export default RoomContext;
