import React from 'react';
import './ObservationPanel.css';

/**
 * ObservationPanel - Displays pending observations from secondary players.
 *
 * This component is shown to the primary (turn-taking) player and allows them
 * to incorporate observations from other players into their turn submission.
 *
 * Props:
 * - observations: Array of observation objects { character_id, character_name, observation_text, submitted_at }
 * - onCopyObservation: Callback when user wants to copy an observation to their input
 * - onDismissObservation: Optional callback to dismiss an observation
 * - primaryCharacterName: Name of the primary player's character
 */
const ObservationPanel = ({
  observations = [],
  onCopyObservation,
  onDismissObservation,
  primaryCharacterName
}) => {
  // Filter out already-included observations
  const pendingObservations = observations.filter(obs => !obs.included_in_turn);

  // Don't render if no pending observations
  if (!pendingObservations || pendingObservations.length === 0) {
    return null;
  }

  const formatTimestamp = (isoString) => {
    if (!isoString) return '';
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <div className="observation-panel">
      <div className="observation-panel-header">
        <span className="observation-panel-icon">👁️</span>
        <h3 className="observation-panel-title">
          Party Observations
        </h3>
        <span className="observation-panel-count">
          {pendingObservations.length}
        </span>
      </div>

      <div className="observation-panel-hint">
        Your party members have shared observations. Click to add to your turn.
      </div>

      <div className="observation-panel-list">
        {pendingObservations.map((observation, index) => (
          <div key={`${observation.character_id}-${index}`} className="observation-item">
            <div className="observation-item-header">
              <span className="observation-character-name">
                {observation.character_name}
              </span>
              <span className="observation-timestamp">
                {formatTimestamp(observation.submitted_at)}
              </span>
            </div>

            <div className="observation-text">
              "{observation.observation_text}"
            </div>

            <div className="observation-actions">
              <button
                className="observation-copy-btn"
                onClick={() => onCopyObservation && onCopyObservation(observation)}
                title="Add this observation to your input"
              >
                <span className="copy-icon">📋</span>
                Add to Turn
              </button>

              {onDismissObservation && (
                <button
                  className="observation-dismiss-btn"
                  onClick={() => onDismissObservation(observation)}
                  title="Dismiss this observation"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ObservationPanel;
