import React from 'react';
import './CombatStatusView.css';

const CombatStatusView = ({ combatStatus, turnInfo, className = '', showHeader = true }) => {
  if (!combatStatus || Object.keys(combatStatus).length === 0) {
    return null;
  }

  // Parse HP and AP strings to get current/max values
  const parseStatString = (statString) => {
    if (!statString || statString === 'Unknown' || statString === 'N/A') {
      return { current: 0, max: 0, displayText: statString };
    }
    const match = statString.match(/(\d+)\/(\d+)/);
    if (match) {
      return {
        current: parseInt(match[1], 10),
        max: parseInt(match[2], 10),
        displayText: statString
      };
    }
    return { current: 0, max: 0, displayText: statString };
  };

  // Calculate health bar percentage
  const getHealthPercentage = (hp) => {
    const parsed = parseStatString(hp);
    if (parsed.max === 0) return 0;
    return (parsed.current / parsed.max) * 100;
  };

  // Get health bar color based on percentage
  const getHealthColor = (percentage) => {
    if (percentage > 75) return '#4caf50'; // Green
    if (percentage > 50) return '#8bc34a'; // Light green
    if (percentage > 25) return '#ff9800'; // Orange
    if (percentage > 0) return '#f44336'; // Red
    return '#666'; // Gray for 0
  };

  // Check if combatant is active
  const isActiveCombatant = (name) => {
    return turnInfo?.active_combatant === name;
  };

  return (
    <div className={`combat-status-view base-view ${className}`}>
      {showHeader && (
        <div className="combat-status-header base-header">
          <div className="combat-status-icon base-icon">⚔️</div>
          <h2 className="combat-status-title base-title">
            Combat Status {turnInfo?.round ? `(Round ${turnInfo.round})` : ''}
          </h2>
        </div>
      )}
      <div className="combat-status-content base-content">
        <div className="combat-status-grid">
          {Object.entries(combatStatus).map(([name, status]) => {
            const hpData = parseStatString(status.hp);
            const apData = parseStatString(status.ap);
            const healthPercentage = getHealthPercentage(status.hp);
            const healthColor = getHealthColor(healthPercentage);
            const isActive = isActiveCombatant(name);

            const isHostile = status.hostile === true;

            return (
              <div
                key={name}
                className={`combatant-card ${isActive ? 'active' : ''} ${hpData.current === 0 ? 'unconscious' : ''} ${isHostile ? 'enemy' : ''}`}
              >
                <div className="combatant-name">
                  {name}
                  {isActive && <span className="active-indicator">⚡</span>}
                  {hpData.current === 0 && <span className="unconscious-indicator">💀</span>}
                </div>
                
                <div className="combatant-stats">
                  <div className="stat-row">
                    <span className="stat-label">HP:</span>
                    <div className="stat-bar-container">
                      <div 
                        className="stat-bar hp-bar" 
                        style={{ 
                          width: `${healthPercentage}%`,
                          backgroundColor: healthColor
                        }}
                      />
                      <span className="stat-value">{hpData.displayText}</span>
                    </div>
                  </div>
                  
                  <div className="stat-row">
                    <span className="stat-label">AP:</span>
                    <div className="stat-value-simple">
                      {apData.displayText}
                    </div>
                  </div>
                  
                  {status.status && status.status.length > 0 && (
                    <div className="stat-row status-effects">
                      <span className="stat-label">Status:</span>
                      <div className="status-effects-list">
                        {status.status.map((effect, idx) => (
                          <span key={idx} className="status-effect-tag">
                            {effect}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default CombatStatusView;
