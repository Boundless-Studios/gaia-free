import React from 'react';

const StatsDisplay = ({ stats, isCompact = false }) => {
  const defaultStats = {
    strength: 10,
    dexterity: 10,
    constitution: 10,
    intelligence: 10,
    wisdom: 10,
    charisma: 10
  };

  const currentStats = { ...defaultStats, ...stats };

  // Calculate ability modifier
  const getModifier = (score) => {
    return Math.floor((score - 10) / 2);
  };

  // Format modifier with + or - sign
  const formatModifier = (modifier) => {
    return modifier >= 0 ? `+${modifier}` : `${modifier}`;
  };

  // Get color based on stat value
  const getStatColor = (value) => {
    if (value >= 18) return '#10b981'; // Green for exceptional
    if (value >= 16) return '#3b82f6'; // Blue for very good
    if (value >= 14) return '#f59e0b'; // Orange for good
    if (value >= 12) return '#e5e7eb'; // Light gray for average
    if (value >= 8) return '#9ca3af';  // Gray for below average
    return '#ef4444'; // Red for poor
  };

  const statEntries = [
    { key: 'strength', label: 'STR', icon: '💪' },
    { key: 'dexterity', label: 'DEX', icon: '🏃' },
    { key: 'constitution', label: 'CON', icon: '❤️' },
    { key: 'intelligence', label: 'INT', icon: '🧠' },
    { key: 'wisdom', label: 'WIS', icon: '👁️' },
    { key: 'charisma', label: 'CHA', icon: '💬' }
  ];

  if (isCompact) {
    return (
      <div className="stats-display stats-compact">
        {statEntries.map(({ key, label }) => {
          const value = currentStats[key];
          const modifier = getModifier(value);
          return (
            <div
              key={key}
              className="stat-compact"
              data-testid={`${key}-stat`}
            >
              <div className="stat-label">{label}</div>
              <div
                className="stat-value"
                style={{ color: getStatColor(value) }}
              >
                {value}
              </div>
              <div className="stat-modifier">
                {formatModifier(modifier)}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="stats-display stats-detailed">
      {statEntries.map(({ key, label, icon }) => {
        const value = currentStats[key];
        const modifier = getModifier(value);
        return (
          <div
            key={key}
            className="stat-detailed"
            data-testid={`${key}-stat`}
          >
            <div className="stat-header">
              <span className="stat-icon">{icon}</span>
              <span className="stat-name">{label}</span>
            </div>
            <div className="stat-values">
              <div
                className="stat-score"
                style={{ color: getStatColor(value) }}
              >
                {value}
              </div>
              <div className="stat-modifier-detailed">
                {formatModifier(modifier)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default StatsDisplay;