import React, { useState } from 'react';
import DiceRoller3D from '../components/dice/DiceRoller3D.jsx';

const DiceRollerTest = () => {
  const [rollHistory, setRollHistory] = useState([]);
  const [stats, setStats] = useState({
    totalRolls: 0,
    criticals: 0,
    critFails: 0,
    average: 0,
  });

  const handleRollComplete = (rollData) => {
    const newHistory = [
      {
        id: Date.now(),
        ...rollData,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...rollHistory.slice(0, 19), // Keep last 20 rolls
    ];

    setRollHistory(newHistory);

    // Update stats
    const totalRolls = stats.totalRolls + 1;
    const criticals = stats.criticals + (rollData.result === rollData.maxValue ? 1 : 0);
    const critFails = stats.critFails + (rollData.result === 1 ? 1 : 0);
    const average = (
      (stats.average * stats.totalRolls + rollData.result) / totalRolls
    ).toFixed(2);

    setStats({ totalRolls, criticals, critFails, average });
  };

  return (
    <div className="dice-test-page">
      <header className="dice-test-header">
        <h1>3D Dice Roller Test</h1>
        <p>WebGL-powered dice rolling with physics and visual effects</p>
      </header>

      <div className="dice-test-content">
        <div className="dice-test-main">
          <DiceRoller3D onRollComplete={handleRollComplete} />
        </div>

        <div className="dice-test-sidebar">
          {/* Stats Panel */}
          <div className="stats-panel">
            <h2>Session Stats</h2>
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-value">{stats.totalRolls}</span>
                <span className="stat-label">Total Rolls</span>
              </div>
              <div className="stat-item critical">
                <span className="stat-value">{stats.criticals}</span>
                <span className="stat-label">Criticals</span>
              </div>
              <div className="stat-item fail">
                <span className="stat-value">{stats.critFails}</span>
                <span className="stat-label">Crit Fails</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{stats.average}</span>
                <span className="stat-label">Average</span>
              </div>
            </div>
          </div>

          {/* Roll History */}
          <div className="history-panel">
            <h2>Roll History</h2>
            <div className="history-list">
              {rollHistory.length === 0 ? (
                <p className="history-empty">No rolls yet. Roll the dice!</p>
              ) : (
                rollHistory.map((roll) => (
                  <div
                    key={roll.id}
                    className={`history-item ${
                      roll.result === roll.maxValue ? 'critical' : ''
                    } ${roll.result === 1 ? 'fail' : ''}`}
                  >
                    <span className="history-dice">{roll.diceType.toUpperCase()}</span>
                    <span className="history-result">{roll.result}</span>
                    <span className="history-time">{roll.timestamp}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Features List */}
      <div className="features-section">
        <h2>Features</h2>
        <ul className="features-list">
          <li>WebGL 3D rendering with Three.js</li>
          <li>Support for D4, D6, D8, D10, D12, D20</li>
          <li>Realistic rolling animation with physics</li>
          <li>Particle effects and ambient lighting</li>
          <li>Critical hit/fail visual feedback</li>
          <li>Roll history tracking</li>
        </ul>
      </div>

      <style>{`
        .dice-test-page {
          min-height: 100vh;
          background: linear-gradient(180deg, #0a0a1a 0%, #1a1a2e 50%, #0f0f1a 100%);
          color: #ffffff;
          padding: 20px;
        }

        .dice-test-header {
          text-align: center;
          padding: 20px 0 40px;
        }

        .dice-test-header h1 {
          font-size: 36px;
          margin: 0 0 8px;
          background: linear-gradient(135deg, #9900ff, #ff00ff);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .dice-test-header p {
          color: #888;
          margin: 0;
          font-size: 16px;
        }

        .dice-test-content {
          display: grid;
          grid-template-columns: 1fr 350px;
          gap: 24px;
          max-width: 1400px;
          margin: 0 auto;
        }

        @media (max-width: 1024px) {
          .dice-test-content {
            grid-template-columns: 1fr;
          }
        }

        .dice-test-main {
          min-width: 0;
        }

        .dice-test-sidebar {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .stats-panel, .history-panel {
          background: rgba(26, 26, 46, 0.8);
          border: 1px solid rgba(153, 0, 255, 0.2);
          border-radius: 12px;
          padding: 20px;
        }

        .stats-panel h2, .history-panel h2 {
          margin: 0 0 16px;
          font-size: 18px;
          color: #9900ff;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .stat-item {
          background: rgba(0, 0, 0, 0.3);
          padding: 12px;
          border-radius: 8px;
          text-align: center;
        }

        .stat-item.critical {
          background: rgba(255, 215, 0, 0.1);
          border: 1px solid rgba(255, 215, 0, 0.3);
        }

        .stat-item.fail {
          background: rgba(255, 0, 0, 0.1);
          border: 1px solid rgba(255, 0, 0, 0.3);
        }

        .stat-value {
          display: block;
          font-size: 28px;
          font-weight: bold;
          color: #ffffff;
        }

        .stat-label {
          display: block;
          font-size: 12px;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-top: 4px;
        }

        .history-list {
          max-height: 400px;
          overflow-y: auto;
        }

        .history-empty {
          color: #666;
          text-align: center;
          font-style: italic;
          padding: 20px;
        }

        .history-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 12px;
          background: rgba(0, 0, 0, 0.3);
          border-radius: 8px;
          margin-bottom: 8px;
          transition: all 0.2s ease;
        }

        .history-item:hover {
          background: rgba(153, 0, 255, 0.1);
        }

        .history-item.critical {
          background: rgba(255, 215, 0, 0.15);
          border: 1px solid rgba(255, 215, 0, 0.3);
        }

        .history-item.fail {
          background: rgba(255, 0, 0, 0.15);
          border: 1px solid rgba(255, 0, 0, 0.3);
        }

        .history-dice {
          font-size: 12px;
          color: #9900ff;
          font-weight: bold;
          min-width: 35px;
        }

        .history-result {
          font-size: 20px;
          font-weight: bold;
          flex: 1;
        }

        .history-time {
          font-size: 11px;
          color: #666;
        }

        .features-section {
          max-width: 1400px;
          margin: 40px auto 0;
          background: rgba(26, 26, 46, 0.5);
          border: 1px solid rgba(153, 0, 255, 0.2);
          border-radius: 12px;
          padding: 20px;
        }

        .features-section h2 {
          margin: 0 0 16px;
          color: #9900ff;
        }

        .features-list {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 12px;
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .features-list li {
          padding: 8px 12px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          font-size: 14px;
        }

        .features-list li::before {
          content: "✓ ";
          color: #00ff88;
        }

        /* Scrollbar styling */
        .history-list::-webkit-scrollbar {
          width: 6px;
        }

        .history-list::-webkit-scrollbar-track {
          background: rgba(0, 0, 0, 0.2);
          border-radius: 3px;
        }

        .history-list::-webkit-scrollbar-thumb {
          background: rgba(153, 0, 255, 0.4);
          border-radius: 3px;
        }

        .history-list::-webkit-scrollbar-thumb:hover {
          background: rgba(153, 0, 255, 0.6);
        }
      `}</style>
    </div>
  );
};

export default DiceRollerTest;
