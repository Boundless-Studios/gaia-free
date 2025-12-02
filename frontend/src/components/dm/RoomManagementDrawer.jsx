/**
 * RoomManagementDrawer Component
 * Full seat management interface for DMs
 * - Seat grid with filtering
 * - Vacate seat functionality
 * - Copy invite link
 * - Start campaign button
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Modal } from '../base-ui/Modal.jsx';
import Button from '../base-ui/Button.jsx';
import { Alert } from '../base-ui/Alert.jsx';
import { useRoom } from '../../contexts/RoomContext.jsx';
import SeatCard from '../room/SeatCard.jsx';
import { useShareInvite } from '../../hooks/useShareInvite.js';

export const RoomManagementDrawer = ({ campaignId, isOpen, onClose }) => {
  const {
    roomState,
    loading,
    vacateSeat,
    startCampaign,
    canStartCampaign,
    isDMSeated,
  } = useRoom();
  const [seatFilter, setSeatFilter] = useState('all');
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Use the same share invite logic as the header share button
  const { fetchToken, copyInviteLink: handleCopyInviteLink, shareState } = useShareInvite(
    campaignId,
    setSuccess
  );
  const campaignActive = roomState?.campaign_status === 'active';
  const campaignStatusLabel = campaignActive ? 'Active' : (roomState?.campaign_status || 'Setup');
  const campaignStatusColor = campaignActive ? 'text-green-400' : 'text-yellow-400';
  const roomStatusLabel = roomState?.room_status === 'active' ? 'DM Connected' : 'Waiting for DM';
  const roomStatusColor = roomState?.room_status === 'active' ? 'text-green-400' : 'text-yellow-400';
  const hasCharacterReady = (roomState?.seats || []).some(
    (seat) => seat.seat_type === 'player' && !!seat.character_id
  );
  const invitedPlayers = roomState?.invited_players || [];
  const startWarningMessage = !isDMSeated
    ? '⚠️ You must join as DM first'
    : roomState?.room_status !== 'active'
    ? '⚠️ Open the DM dashboard to connect before starting'
    : !hasCharacterReady
    ? '⚠️ At least one player seat must have a character'
    : '⚠️ Waiting for prerequisites';
  const visibleInvitees = useMemo(
    () =>
      invitedPlayers.filter(
        (player) =>
          player &&
          (player.display_name || player.email || player.user_id)
      ),
    [invitedPlayers]
  );
  const renderInviteStatus = (player) => {
    let statusLabel = 'Invited';
    let statusClass = 'bg-gray-800/70 text-gray-300';
    if (player.status === 'accepted') {
      statusLabel = 'Accepted';
      statusClass = 'bg-blue-900/40 text-blue-300';
    } else if (player.status === 'seated') {
      statusLabel = 'Seated';
      statusClass = 'bg-green-900/40 text-green-300';
    }
    return (
      <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide ${statusClass}`}>
        {statusLabel}
      </span>
    );
  };
  const renderInviteeRow = (player, index) => {
    const display = player.display_name || player.email || 'Pending invite';
    const seatLabel =
      typeof player.seat_slot_index === 'number'
        ? `Seat ${player.seat_slot_index + 1}`
        : player.seat_id
        ? 'Seat'
        : null;
    return (
      <div
        key={player.user_id || player.email || `invite-${index}`}
        className="flex flex-wrap items-center gap-2 text-sm text-gray-300"
      >
        <span className="font-medium">{display}</span>
        {renderInviteStatus(player)}
        {player.is_online && (
          <span className="flex items-center gap-1 text-xs text-green-400">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            Online
          </span>
        )}
        {seatLabel && (
          <span className="text-xs text-gray-400">
            {seatLabel}
          </span>
        )}
      </div>
    );
  };

  useEffect(() => {
    if (!isOpen) return;
    console.debug('[RoomManagementDrawer] open -> seats snapshot', {
      campaignId,
      dmSeat: roomState?.seats?.find(s => s.seat_type === 'dm'),
      allSeats: roomState?.seats,
      isDMSeated,
    });
  }, [campaignId, isDMSeated, isOpen, roomState?.seats]);

  // Filter seats by status
  const filteredSeats = useMemo(() => {
    if (!roomState?.seats) return [];
    if (seatFilter === 'all') return roomState.seats;

    return roomState.seats.filter(seat => {
      switch (seatFilter) {
        case 'available':
          return !seat.owner_user_id;
        case 'occupied':
          return seat.owner_user_id && seat.character_id;
        case 'offline':
          return seat.owner_user_id && !seat.online;
        default:
          return true;
      }
    });
  }, [roomState?.seats, seatFilter]);

  // Seat counts for filter chips
  const seatCounts = useMemo(() => {
    if (!roomState?.seats) return { all: 0, available: 0, occupied: 0, offline: 0 };

    return {
      all: roomState.seats.length,
      available: roomState.seats.filter(s => !s.owner_user_id).length,
      occupied: roomState.seats.filter(s => s.owner_user_id && s.character_id).length,
      offline: roomState.seats.filter(s => s.owner_user_id && !s.online).length,
    };
  }, [roomState?.seats]);

  const handleVacateSeat = async (seatId) => {
    setError(null);
    setSuccess(null);

    try {
      await vacateSeat(seatId, true);
      setSuccess('Seat vacated successfully');
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      console.error('Failed to vacate seat:', err);
      setError(err.message || 'Failed to vacate seat');
    }
  };

  const handleStartCampaign = async () => {
    setError(null);
    setSuccess(null);
    setIsStarting(true);

    try {
      await startCampaign();
      setSuccess('Campaign started! Refreshing page...');
      // Refresh page to ensure UI updates properly
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err) {
      console.error('Failed to start campaign:', err);
      setError(err.message || 'Failed to start campaign');
      setIsStarting(false);
    }
  };

  // Copy invite link with proper invite token
  const copyInviteLink = async () => {
    if (!campaignId) {
      setError('Campaign ID unavailable. Try reopening the drawer.');
      return;
    }

    // If we don't have a token yet, fetch it first
    if (!shareState.token && !shareState.loading) {
      await fetchToken(false);
    }

    // Copy the invite link using the hook's function
    await handleCopyInviteLink();
  };

  // Filter chip component
  const FilterChip = ({ filter, label, count }) => {
    const isActive = seatFilter === filter;
    return (
      <button
        onClick={() => setSeatFilter(filter)}
        className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all
          ${isActive
            ? 'bg-purple-600 text-white'
            : 'bg-gray-800 text-gray-300 hover:bg-gray-700 border border-purple-600/20'
          }`}
      >
        {label} ({count})
      </button>
    );
  };

  if (loading) {
    return (
      <Modal open={isOpen} onClose={onClose} title="Room Management" width="max-w-4xl">
        <div className="p-8 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin h-8 w-8 border-4 border-purple-500 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-gray-400">Loading room state...</p>
          </div>
        </div>
      </Modal>
    );
  }

  // Show error if room state failed to load
  if (!roomState) {
    return (
      <Modal open={isOpen} onClose={onClose} title="Room Management" width="max-w-4xl">
        <div className="p-8 flex items-center justify-center">
          <Alert variant="error">
            Failed to load room state. Please try again.
          </Alert>
        </div>
      </Modal>
    );
  }

  return (
    <Modal open={isOpen} onClose={onClose} title="Room Management" width="max-w-5xl">
      <div className="room-management-content p-6 overflow-y-auto max-h-[calc(90vh-120px)]">
        {/* Alerts */}
        {error && (
          <Alert variant="error" className="mb-4" onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert variant="success" className="mb-4" onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        {/* Header actions */}
        <div className="header-actions mb-6 flex items-start gap-3 flex-wrap">
          <Button
            onClick={copyInviteLink}
            variant="secondary"
            icon={
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            }
          >
            Copy Invite Link
          </Button>

          <div className="invite-summary flex flex-col gap-1 min-w-[220px]">
            <div className="text-xs uppercase tracking-wide text-gray-500">Invited Players</div>
            {visibleInvitees.length === 0 ? (
              <div className="text-sm text-gray-500">No invitations sent yet</div>
            ) : (
              visibleInvitees.map(renderInviteeRow)
            )}
          </div>

          <div className="flex-1" />

          <div className="text-sm text-gray-400 flex flex-col sm:flex-row sm:items-center gap-2">
            <span>
              Room Status:{' '}
              <span className={`font-medium ${roomStatusColor}`}>
                {roomStatusLabel}
              </span>
            </span>
            <span>
              Campaign Status:{' '}
              <span className={`font-medium ${campaignStatusColor}`}>
                {campaignStatusLabel}
              </span>
            </span>
          </div>
        </div>

        {/* Seat filter chips */}
        <div className="filter-chips mb-6 flex gap-2 flex-wrap">
          <FilterChip filter="all" label="All" count={seatCounts.all} />
          <FilterChip filter="available" label="Available" count={seatCounts.available} />
          <FilterChip filter="occupied" label="Occupied" count={seatCounts.occupied} />
          <FilterChip filter="offline" label="Offline" count={seatCounts.offline} />
        </div>

        {/* Seat Grid */}
        <div className="seat-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {filteredSeats.map(seat => (
            <SeatCard
              key={seat.seat_id}
              seat={seat}
              onVacate={handleVacateSeat}
              isDM={true}
            />
          ))}
        </div>

        {filteredSeats.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No seats match the current filter
          </div>
        )}

        {/* Start Campaign Section */}
        <div className="start-campaign-section mt-8 pt-6 border-t border-purple-600/20">
          <Button
            onClick={handleStartCampaign}
            disabled={campaignActive || !canStartCampaign || isStarting}
            loading={isStarting && !campaignActive}
            variant="primary"
            size="large"
            fullWidth
          >
            {campaignActive
              ? 'Campaign Active'
              : isStarting
              ? 'Starting Campaign...'
              : 'Start Campaign'}
          </Button>

          {campaignActive && (
            <div className="mt-3 text-center text-sm text-green-400">
              ✓ Campaign already started. Manage the session from the dashboard.
            </div>
          )}

          {!campaignActive && !canStartCampaign && (
            <div className="mt-3 text-center text-sm text-yellow-400">
              {startWarningMessage}
            </div>
          )}

          {!campaignActive && canStartCampaign && !isStarting && (
            <div className="mt-3 text-center text-sm text-gray-400">
              ✓ Ready to start! This will generate the opening narrative.
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default RoomManagementDrawer;
