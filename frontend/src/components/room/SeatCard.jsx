/**
 * SeatCard Component
 * Displays a seat with 5 different states:
 * 1. Available (Empty)
 * 2. Available (With Character)
 * 3. Reserved (Creating Character)
 * 4. Occupied (Online)
 * 5. Occupied (Offline)
 */

import React from 'react';
import { Card, CardHeader, CardContent, CardFooter, CardTitle } from '../base-ui/Card.jsx';
import Button from '../base-ui/Button.jsx';

export const SeatCard = ({ seat, onSelect, onVacate, disabled, isDM = false }) => {
  console.debug('[SeatCard] render', {
    seatId: seat.seat_id,
    seatType: seat.seat_type,
    owner: seat.owner_user_id,
    ownerDisplay: seat.owner_display_name || seat.owner_email,
    hasCharacter: seat.character_id,
    online: seat.online,
  });
  const isDMSeat = seat.seat_type === 'dm';
  const hasOwner = Boolean(seat.owner_user_id);
  const hasCharacter = seat.character_id !== null;
  const isAvailable = !hasOwner;
  const isReserved = hasOwner && !hasCharacter && !isDMSeat;
  const isOccupied = hasOwner && hasCharacter;

  // Get status badge
  const getStatusBadge = () => {
    if (!hasOwner) {
      return (
        <span className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-300">
          Available
        </span>
      );
    }

    if (isDMSeat) {
      if (seat.online) {
        return (
          <span className="px-2 py-1 text-xs rounded bg-green-900/30 text-green-400 flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
            DM Active
          </span>
        );
      }
      return (
        <span className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-400 flex items-center gap-1 opacity-70">
          <span className="w-2 h-2 rounded-full border border-gray-400" />
          DM Offline
        </span>
      );
    }

    if (!seat.character_id) {
      return (
        <span className="px-2 py-1 text-xs rounded bg-yellow-900/30 text-yellow-400 flex items-center gap-1 animate-pulse">
          <svg className="animate-spin h-3 w-3" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Creating...
        </span>
      );
    }

    if (seat.online) {
      return (
        <span className="px-2 py-1 text-xs rounded bg-green-900/30 text-green-400 flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Online
        </span>
      );
    }

    return (
      <span className="px-2 py-1 text-xs rounded bg-gray-700 text-gray-400 flex items-center gap-1 opacity-70">
        <span className="w-2 h-2 rounded-full border border-gray-400" />
        Offline
      </span>
    );
  };

  // Get profile image or initials
  const getProfileImage = () => {
    if (!isDMSeat && seat.character_avatar_url) {
      return (
        <img
          src={seat.character_avatar_url}
          alt={seat.character_name || 'Character'}
          className={`w-16 h-16 rounded-full object-cover ${!seat.online ? 'opacity-50 grayscale' : ''}`}
        />
      );
    }

    // Initials fallback
    const initials = seat.character_name?.[0] || seat.owner_display_name?.[0] || seat.owner_email?.[0] || '?';
    return (
      <div className={`w-16 h-16 rounded-full bg-purple-900/40 flex items-center justify-center text-2xl font-bold text-purple-300 ${!seat.online ? 'opacity-50' : ''}`}>
        {initials}
      </div>
    );
  };

  // Seat label
  const getSeatLabel = () => {
    if (seat.seat_type === 'dm') {
      return 'DM Seat';
    }
    return `Seat ${(seat.slot_index ?? 0) + 1}`;
  };

  return (
    <Card className={`seat-card ${isAvailable ? '' : 'border-purple-500/30'} ${!seat.online && isOccupied ? 'opacity-75' : ''}`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            {getSeatLabel()}
          </CardTitle>
          {getStatusBadge()}
        </div>
      </CardHeader>

      <CardContent>
        {hasCharacter && !isDMSeat ? (
          <div className="seat-character flex items-center gap-3">
            {getProfileImage()}
            <div className="character-info flex-1 min-w-0">
              <h4 className="font-semibold text-gray-100 truncate">
                {seat.character_name || 'Unknown Character'}
              </h4>
              {seat.owner_user_id && (
                <p className="text-sm text-gray-400 truncate">
                  {seat.owner_display_name || seat.owner_email || 'Unknown Player'}
                </p>
              )}
            </div>
          </div>
        ) : hasOwner ? (
          <div className="seat-reserved py-4">
            {isDMSeat ? (
              <>
                <p className="text-sm text-gray-300">
                  DM: <span className="text-purple-300 font-medium">{seat.owner_display_name || seat.owner_email || 'Unknown'}</span>
                </p>
                <p className="text-xs text-gray-500 mt-1">Hosting and managing the room</p>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-300">
                  Reserved by <span className="text-purple-300 font-medium">{seat.owner_display_name || seat.owner_email || 'Unknown'}</span>
                </p>
                <p className="text-xs text-gray-500 mt-1">Creating character...</p>
              </>
            )}
          </div>
        ) : (
          <div className="seat-empty py-4">
            <p className="text-gray-500 text-center">Empty seat</p>
          </div>
        )}
      </CardContent>

      <CardFooter>
        {isAvailable && !isDM ? (
          <Button
            onClick={() => onSelect?.(seat.seat_id)}
            disabled={disabled}
            variant="primary"
            fullWidth
          >
            {hasCharacter ? 'Occupy Seat' : 'Select Seat'}
          </Button>
        ) : isAvailable && isDM ? (
          <div className="text-center text-sm text-gray-500">
            Available for players
          </div>
        ) : isDM ? (
          <div className="flex gap-2">
            <div className="flex-1 text-sm text-gray-400 flex items-center">
              {seat.online ? '✓ Active' : '○ Idle'}
            </div>
            {seat.seat_type !== 'dm' && (
              <Button
                onClick={() => onVacate?.(seat.seat_id)}
                disabled={disabled}
                variant="secondary"
                size="small"
              >
                Vacate
              </Button>
            )}
          </div>
        ) : (
          <Button disabled variant="secondary" fullWidth>
            {isReserved ? 'Reserved' : seat.online ? 'Occupied' : 'Claimed'}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
};

export default SeatCard;
