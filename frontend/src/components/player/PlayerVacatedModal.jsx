import React from 'react';
import { Modal } from '../base-ui/Modal.jsx';
import { Button } from '../base-ui/Button.jsx';

const PlayerVacatedModal = ({ open, onConfirm, seatLabel = 'your seat' }) => (
  <Modal
    open={open}
    onClose={onConfirm}
    title="Seat Released"
    width="max-w-md"
    preventBackdropClose
    showCloseButton={false}
  >
    <div className="space-y-4 text-sm text-gray-200">
      <p>
        The DM vacated {seatLabel}. This usually means they need to free the spot
        for someone else or reset the character. You can immediately pick another open seat.
      </p>
      <div className="flex justify-end">
        <Button variant="primary" onClick={onConfirm}>
          Choose a seat
        </Button>
      </div>
    </div>
  </Modal>
);

export default PlayerVacatedModal;
