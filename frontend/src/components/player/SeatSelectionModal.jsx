import React, { useMemo } from 'react';
import { Modal } from '../base-ui/Modal.jsx';
import { Alert } from '../base-ui/Alert.jsx';
import Button from '../base-ui/Button.jsx';
import SeatCard from '../room/SeatCard.jsx';

const SeatSelectionModal = ({
  open,
  onClose,
  requireSelection = false,
  seats = [],
  selectingSeatId = null,
  onSelectSeat,
  onRefresh,
  errorMessage = null,
  roomStatus = null,
}) => {
  const sortedSeats = useMemo(() => {
    return [...seats].sort((a, b) => (a.slot_index ?? 0) - (b.slot_index ?? 0));
  }, [seats]);

  const statusCopy = useMemo(() => {
    if (!roomStatus) return 'Select a seat to join the table.';
    if (roomStatus === 'waiting_for_dm') {
      return 'Select a seat and wait for your DM to arrive.';
    }
    if (roomStatus === 'active') {
      return 'Pick a seat to jump into the ongoing adventure.';
    }
    return 'Select a seat to join the table.';
  }, [roomStatus]);

  const modalTitle = requireSelection ? 'Claim Your Seat' : 'Choose a Seat';
  const modalOnClose = requireSelection ? () => {} : onClose;

  return (
    <Modal
      open={open}
      onClose={modalOnClose}
      title={modalTitle}
      width="max-w-5xl"
      showCloseButton={!requireSelection}
      preventBackdropClose={requireSelection}
    >
      <div className="space-y-4">
        <div>
          <p className="text-gray-300 text-sm">{statusCopy}</p>
          <p className="text-gray-500 text-xs mt-1">
            Seats persist between sessions. Once you claim one, your character stays bound to it until the DM vacates you.
          </p>
        </div>

        {errorMessage && (
          <Alert variant="error">
            {errorMessage}
          </Alert>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedSeats.map((seat) => (
            <SeatCard
              key={seat.seat_id}
              seat={seat}
              onSelect={onSelectSeat}
              disabled={Boolean(selectingSeatId && selectingSeatId !== seat.seat_id)}
            />
          ))}
          {sortedSeats.length === 0 && (
            <div className="col-span-full">
              <Alert variant="info">
                No seats are configured for this campaign yet. Ask your DM to set up the room.
              </Alert>
            </div>
          )}
        </div>

        <div className="flex justify-between items-center pt-2 border-t border-purple-800/30">
          <div className="text-xs text-gray-400">
            {selectingSeatId ? 'Claiming seat...' : 'Only you and invited players can see this list.'}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={onRefresh}
            disabled={Boolean(selectingSeatId)}
          >
            🔄 Refresh seats
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default SeatSelectionModal;
