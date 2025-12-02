import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import apiService from '../services/apiService';
import { Modal } from './base-ui/Modal';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from './base-ui/Card';
import { Button } from './base-ui/Button';
import { Alert } from './base-ui/Alert';

const PlayerSessionModal = ({ onClose, isOpen }) => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionSummaries, setSessionSummaries] = useState({});

  useEffect(() => {
    if (isOpen) {
      fetchSessions();
    }
  }, [isOpen]);

  const fetchSessions = async () => {
    setLoading(true);
    setError(null);
    setSessionSummaries({});
    try {
      // Use role: 'player' to get all campaigns the user can access (owned OR member).
      const data = await apiService.listSimpleCampaigns({ role: 'player' });

      if (data?.campaigns) {
        // Sort by last played (most recent first)
        const sortedSessions = [...data.campaigns].sort((a, b) => {
          const aTime = new Date(a.last_played || a.updated_at || a.created_at || 0).getTime();
          const bTime = new Date(b.last_played || b.updated_at || b.created_at || 0).getTime();
          return bTime - aTime; // Most recent first
        });

        // Fetch summaries for campaigns the player can access
        const summaryResponse = await apiService.listRoomSummaries({ role: 'player' });
        const summaryMap = {};
        (summaryResponse?.summaries || []).forEach((summary) => {
          if (summary?.campaign_id) {
            summaryMap[summary.campaign_id] = summary;
          }
        });

        const filteredSessions = sortedSessions.filter((session) => {
          const campaignId = session.id || session.session_id;
          return Boolean(campaignId && summaryMap[campaignId]);
        });

        setSessions(filteredSessions);
        setSessionSummaries(summaryMap);
      } else {
        setSessions([]);
      }
    } catch (err) {
      console.error('Error fetching player sessions:', err);
      setError(err.message || 'Failed to load sessions');
      setSessions([]);
      setSessionSummaries({});
    } finally {
      setLoading(false);
    }
  };

  const handleJoinSession = (sessionId) => {
    // Navigate to player view for this session
    navigate(`/${sessionId}/player`);
    if (onClose) {
      onClose();
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return 'Never';

    // Show relative time for recent dates
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;

    return date.toLocaleDateString();
  };

  const getRoomStatusMeta = (roomStatus) => {
    switch (roomStatus) {
      case 'active':
        return { label: 'Active Campaign', badgeClass: 'bg-emerald-900/60 text-emerald-200 border border-emerald-700/60' };
      case 'paused':
        return { label: 'Paused', badgeClass: 'bg-amber-900/60 text-amber-200 border border-amber-700/60' };
      case 'waiting_for_dm':
        return { label: 'Waiting for DM', badgeClass: 'bg-slate-800 text-amber-200 border border-slate-700' };
      case 'waiting_for_players':
        return { label: 'Waiting for Players', badgeClass: 'bg-indigo-900/60 text-indigo-200 border border-indigo-700/60' };
      default:
        return { label: 'Status Unknown', badgeClass: 'bg-slate-800 text-slate-200 border border-slate-700' };
    }
  };

  const buildSessionsWithSummaries = useMemo(() => {
    if (!sessions?.length) {
      return [];
    }
    return sessions.map((session) => {
      const campaignId = session.id || session.session_id;
      return {
        ...session,
        campaignId,
        summary: campaignId ? sessionSummaries[campaignId] : null,
      };
    });
  }, [sessions, sessionSummaries]);

  const buildJoinCta = (summary) => {
    const hasSeat = Boolean(summary?.user_seat_id);
    if (hasSeat) {
      const label = summary?.user_character_name
        ? `Resume as ${summary.user_character_name}`
        : 'Resume Session';
      return { label, disabled: false, variant: 'primary' };
    }
    const maxSeats = summary?.max_player_seats ?? 0;
    const filledSeats = summary?.filled_player_seats ?? 0;
    const isFull = maxSeats > 0 && filledSeats >= maxSeats;
    if (isFull) {
      return { label: 'Room Full', disabled: true, variant: 'secondary' };
    }
    return { label: 'Join Session', disabled: false, variant: 'primary' };
  };

  const renderSeatAvailability = (summary) => {
    const maxSeats = Number.isFinite(summary?.max_player_seats)
      ? summary.max_player_seats
      : null;
    const filledSeats = summary?.filled_player_seats ?? 0;
    if (maxSeats === null || maxSeats <= 0) {
      return 'Seat data unavailable';
    }
    const availableSeats = Math.max(maxSeats - filledSeats, 0);
    if (availableSeats === 0) {
      return 'No open seats';
    }
    if (availableSeats === 1) {
      return '1 seat available';
    }
    return `${availableSeats} seats available`;
  };

  const renderDmPresence = (summary) => {
    const dmOnline = summary?.room_status && summary.room_status !== 'waiting_for_dm';
    return (
      <span className={`flex items-center gap-1 text-xs font-medium ${dmOnline ? 'text-emerald-300' : 'text-gray-400'}`}>
        <span className={`h-2 w-2 rounded-full ${dmOnline ? 'bg-emerald-400' : 'bg-gray-500'}`} />
        {dmOnline ? 'DM Online' : 'DM Offline'}
      </span>
    );
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Join a Session"
      width="max-w-3xl"
      className="h-[80vh]"
    >
      <div className="flex flex-col h-full">
        {/* Header Info */}
        <div className="mb-4">
          <p className="text-gray-400 text-sm">
            Select a campaign session to join as a player
          </p>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="text-center py-8 text-gray-400">
              <div className="animate-pulse">Loading sessions...</div>
            </div>
          ) : error ? (
            <Alert variant="error">
              {error}
            </Alert>
          ) : sessions.length === 0 ? (
            <Alert variant="info">
              <div className="text-center py-4">
                <p className="mb-2">No sessions available.</p>
                <p className="text-sm text-gray-400">
                  Ask your Dungeon Master to invite you to a campaign session.
                </p>
              </div>
            </Alert>
          ) : (
            <div className="space-y-3">
              {buildSessionsWithSummaries.map((session) => {
                const summary = session.summary;
                const roomStatusMeta = getRoomStatusMeta(summary?.room_status);
                const seatLabel = summary
                  ? `${summary.filled_player_seats ?? 0} / ${summary.max_player_seats ?? 0} seats`
                  : 'Seats: Unknown';
                const seatAvailability = renderSeatAvailability(summary);
                const cta = buildJoinCta(summary);
                const hasSeat = Boolean(summary?.user_seat_id);
                const dmPresencePill = renderDmPresence(summary);

                return (
                  <Card
                    key={session.campaignId || session.id}
                    hover
                  >
                    <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
                        <span role="img" aria-label="Campaign">
                          ⚔️
                        </span>
                        <span>{session.name || session.title}</span>
                      </CardTitle>
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full uppercase tracking-wide ${roomStatusMeta.badgeClass}`}
                        >
                          {roomStatusMeta.label}
                        </span>
                        {dmPresencePill}
                        {hasSeat && (
                          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-900/50 text-emerald-200 border border-emerald-700/60">
                            Seat Reserved
                          </span>
                        )}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid gap-3 text-sm text-gray-300 sm:grid-cols-2">
                        <div className="space-y-2">
                          {session.owner_email && (
                            <div>
                              <span className="text-gray-500">Dungeon Master:</span>{' '}
                              <span className="text-gray-300">{session.owner_email}</span>
                            </div>
                          )}
                          <div>
                            <span className="text-gray-500">Last Played:</span>{' '}
                            <span className="text-gray-300">
                              {formatDate(session.last_played || session.updated_at || session.created_at)}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500">
                            Session ID: {session.campaignId || session.id}
                          </div>
                        </div>
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 font-semibold text-white">
                            <span>{seatLabel}</span>
                            {summary && (
                              <span
                                className={`text-[0.65rem] px-2 py-0.5 rounded-full border ${
                                  summary.max_player_seats && summary.filled_player_seats >= summary.max_player_seats
                                    ? 'bg-rose-900/40 text-rose-200 border-rose-800/80'
                                    : 'bg-emerald-900/30 text-emerald-200 border-emerald-800/60'
                                }`}
                              >
                                {summary.max_player_seats && summary.filled_player_seats >= summary.max_player_seats
                                  ? 'Full'
                                  : 'Open Seats'}
                              </span>
                            )}
                          </div>
                          <div className="text-gray-400 text-xs">
                            {summary ? seatAvailability : 'Loading seat availability...'}
                          </div>
                          {summary?.user_character_name && (
                            <div className="text-xs text-emerald-300">
                              Resuming as <span className="font-semibold">{summary.user_character_name}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                    <CardFooter className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      {session.members && session.members.length > 0 && (
                        <div className="text-xs text-gray-500 w-full sm:w-auto">
                          Players:{' '}
                          <span className="text-gray-300">
                            {Array.isArray(session.members)
                              ? session.members.join(', ')
                              : String(session.members)}
                          </span>
                        </div>
                      )}
                      <Button
                        onClick={() => handleJoinSession(session.campaignId || session.id)}
                        variant={cta.variant}
                        size="sm"
                        className="w-full sm:w-auto"
                        disabled={cta.disabled}
                      >
                        {cta.label}
                      </Button>
                    </CardFooter>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="mt-4 pt-4 border-t border-gaia-light">
          <div className="flex justify-between items-center">
            <Button
              onClick={fetchSessions}
              variant="ghost"
              size="sm"
              disabled={loading}
            >
              🔄 Refresh
            </Button>
            <Button
              onClick={onClose}
              variant="secondary"
            >
              Close
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
};

export default PlayerSessionModal;
