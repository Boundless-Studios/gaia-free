import React from 'react';

const ProgressIndicator = ({ turnInfo }) => {
  if (!turnInfo) return null;

  const {
    turn_number = 1,
    character_name = 'Player',
    available_actions = [],
    turn_id
  } = turnInfo;

  // Calculate progress based on turn number (simple visualization)
  const progressPercent = Math.min((turn_number / 10) * 100, 100);

  return (
    <div className="progress-indicator">
      <div className="progress-header">
        <div className="progress-info">
          <span className="progress-icon">⚡</span>
          <span className="progress-text">
            Turn {turn_number} - {character_name}
          </span>
        </div>
        <div className="progress-actions">
          <span className="actions-count">
            {available_actions.length} action{available_actions.length !== 1 ? 's' : ''} available
          </span>
        </div>
      </div>

      <div className="progress-bar-container">
        <div
          className="progress-bar"
          style={{ width: `${progressPercent}%` }}
        >
          <div className="progress-glow"></div>
        </div>
      </div>

      {available_actions.length > 0 && (
        <div className="quick-actions">
          {available_actions.slice(0, 6).map((action, index) => (
            <span key={action.action_id || index} className="quick-action">
              {action.name || action.description}
            </span>
          ))}
          {available_actions.length > 6 && (
            <span className="more-actions">
              +{available_actions.length - 6} more
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export default ProgressIndicator;