import React, { useState } from 'react';

const AbilitiesPanel = ({ abilities = [], isExpanded = false }) => {
  const [selectedAbility, setSelectedAbility] = useState(null);

  // Default abilities for demonstration
  const defaultAbilities = [
    {
      id: 'rage',
      name: 'Rage',
      type: 'feature',
      description: 'Enter a battle rage that grants bonus damage and resistance to physical damage.',
      uses: { current: 2, max: 2, resetOn: 'long_rest' },
      icon: '😡'
    },
    {
      id: 'unarmored_defense',
      name: 'Unarmored Defense',
      type: 'passive',
      description: 'While not wearing armor, your AC equals 10 + Dex modifier + Con modifier.',
      icon: '🛡️'
    }
  ];

  const currentAbilities = abilities.length > 0 ? abilities : defaultAbilities;

  const getAbilityTypeColor = (type) => {
    switch (type) {
      case 'spell': return '#8b5cf6';
      case 'feature': return '#f59e0b';
      case 'passive': return '#10b981';
      case 'cantrip': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  const getAbilityTypeIcon = (type) => {
    switch (type) {
      case 'spell': return '✨';
      case 'feature': return '⚡';
      case 'passive': return '🔷';
      case 'cantrip': return '🌟';
      default: return '📜';
    }
  };

  if (!isExpanded && currentAbilities.length === 0) {
    return (
      <div className="abilities-panel abilities-empty">
        <div className="empty-message">
          <span className="empty-icon">📜</span>
          <span>No abilities available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="abilities-panel">
      <div className="abilities-list">
        {currentAbilities.map((ability) => (
          <div
            key={ability.id}
            className={`ability-item ${selectedAbility === ability.id ? 'selected' : ''}`}
            onClick={() => setSelectedAbility(
              selectedAbility === ability.id ? null : ability.id
            )}
          >
            {/* Ability Header */}
            <div className="ability-header">
              <div className="ability-icon">
                {ability.icon || getAbilityTypeIcon(ability.type)}
              </div>
              <div className="ability-title">
                <div className="ability-name">{ability.name}</div>
                <div
                  className="ability-type"
                  style={{ color: getAbilityTypeColor(ability.type) }}
                >
                  {ability.type}
                </div>
              </div>
              {ability.uses && (
                <div className="ability-uses">
                  <span className="uses-current">{ability.uses.current}</span>
                  <span className="uses-separator">/</span>
                  <span className="uses-max">{ability.uses.max}</span>
                </div>
              )}
            </div>

            {/* Ability Description (Expandable) */}
            {selectedAbility === ability.id && (
              <div className="ability-description">
                <p>{ability.description}</p>
                {ability.uses && (
                  <div className="ability-details">
                    <div className="detail-item">
                      <span className="detail-label">Resets on:</span>
                      <span className="detail-value">
                        {ability.uses.resetOn.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      {isExpanded && (
        <div className="abilities-actions">
          <button className="ability-action-btn">
            <span className="btn-icon">🎲</span>
            <span>Roll Initiative</span>
          </button>
          <button className="ability-action-btn">
            <span className="btn-icon">🛡️</span>
            <span>Defensive Stance</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default AbilitiesPanel;