import React, { useMemo, useState } from 'react';
import { Modal } from '../base-ui/Modal.jsx';
import { Alert } from '../base-ui/Alert.jsx';
import { Button } from '../base-ui/Button.jsx';
import SeatCharacterEditor from '../room/SeatCharacterEditor.jsx';
import apiService from '../../services/apiService.js';

const CharacterAssignmentModal = ({
  open,
  seat,
  draft,
  onDraftChange,
  onSubmit,
  onCancel,
  isSubmitting = false,
  errorMessage = null,
  campaignId,
}) => {
  const [autofillError, setAutofillError] = useState(null);
  const [autofilling, setAutofilling] = useState(false);

  const seatLabel = useMemo(() => {
    if (!seat) return 'your seat';
    if (seat.slot_index === null || seat.slot_index === undefined) {
      return 'your seat';
    }
    return `Seat ${seat.slot_index + 1}`;
  }, [seat]);

  const updateField = (field, value) => {
    if (!onDraftChange) return;
    onDraftChange({
      ...(draft || {}),
      [field]: value,
    });
  };

  const handleBulkChange = (updates) => {
    if (!onDraftChange) return;
    onDraftChange({
      ...(draft || {}),
      ...updates,
    });
  };

  const handleAutofill = async () => {
    if (!seat) return;
    setAutofilling(true);
    setAutofillError(null);
    try {
      const payload = {
        slot_id: seat.slot_index ?? 0,
        inspiration: {
          role: seat.slot_index !== undefined ? `Seat ${seat.slot_index + 1}` : undefined,
        },
      };
      const response = await apiService.generateCharacter(payload);
      if (response?.success && response.character) {
        onDraftChange({
          ...(draft || {}),
          ...response.character,
        });
      } else {
        setAutofillError(response?.error || 'Failed to generate character');
      }
    } catch (err) {
      console.error('Failed to auto-fill character', err);
      setAutofillError(err.message || 'Failed to generate character');
    } finally {
      setAutofilling(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit?.(draft);
  };

  return (
    <Modal
      open={open}
      onClose={onCancel || (() => {})}
      title="Create Your Character"
      width="max-w-5xl"
      showCloseButton={Boolean(onCancel)}
      preventBackdropClose={!onCancel}
    >
      {!draft ? (
        <div className="text-center text-gray-400 py-6">
          Loading seat details...
        </div>
      ) : (
        <form className="space-y-6" onSubmit={handleSubmit}>
          <p className="text-gray-300 text-sm">
            {seatLabel} is yours! Describe your hero so the DM can weave them into the story.
          </p>

          {(errorMessage || autofillError) && (
            <Alert variant="error">
              {errorMessage || autofillError}
            </Alert>
          )}

          <SeatCharacterEditor
            seat={seat}
            title={seatLabel}
            character={draft}
            campaignId={campaignId}
            showVoiceSelect={false}
            headerContent={(
              <Button
                type="button"
                variant="secondary"
                onClick={handleAutofill}
                disabled={autofilling}
              >
                {autofilling ? '✨ Generating...' : '✨ Inspire Me'}
              </Button>
            )}
            onFieldChange={updateField}
            onBulkChange={handleBulkChange}
          />

          <div className="flex justify-end items-center gap-3 border-t border-purple-800/40 pt-4">
            {onCancel && (
              <Button
                type="button"
                variant="ghost"
                onClick={onCancel}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            )}
            <Button
              type="submit"
              variant="primary"
              disabled={isSubmitting || !draft.name || !draft.race || !draft.character_class}
            >
              {isSubmitting ? 'Saving...' : 'Save Character'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};

export default CharacterAssignmentModal;
