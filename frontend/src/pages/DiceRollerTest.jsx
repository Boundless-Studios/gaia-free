import React, { useState, useRef } from 'react';
import DiceRoller3D, { DICE_CONFIGS } from '../components/dice/DiceRoller3D.jsx';
import DiceTrigger from '../components/dice/DiceTrigger.jsx';
import DiceRollModal from '../components/dice/DiceRollModal.jsx';

const DiceRollerTest = () => {
  const [rollHistory, setRollHistory] = useState([]);
  const [stats, setStats] = useState({
    totalRolls: 0,
    criticals: 0,
    critFails: 0,
    average: 0,
  });

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalConfig, setModalConfig] = useState({
    diceToRoll: [{ type: 'd20', count: 1 }],
    modifier: 0,
    rollLabel: 'Dice Roll',
  });

  // Ref for programmatic rolling
  const diceRollerRef = useRef(null);

  const handleRollComplete = (rollData) => {
    const newHistory = [
      {
        id: Date.now(),
        ...rollData,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...rollHistory.slice(0, 19),
    ];

    setRollHistory(newHistory);

    // Update stats
    const totalRolls = stats.totalRolls + 1;
    const criticals = stats.criticals + (rollData.isCritical ? 1 : 0);
    const critFails = stats.critFails + (rollData.isFail ? 1 : 0);
    const average = (
      (stats.average * stats.totalRolls + rollData.result) / totalRolls
    ).toFixed(2);

    setStats({ totalRolls, criticals, critFails, average });
  };

  const handleModalRollComplete = (data) => {
    // Add each result to history
    data.results.forEach(result => {
      const newEntry = {
        id: Date.now() + Math.random(),
        diceType: result.diceType,
        result: result.result,
        maxValue: DICE_CONFIGS[result.diceType]?.faces || 20,
        isCritical: result.result === DICE_CONFIGS[result.diceType]?.faces,
        isFail: result.result === 1,
        timestamp: new Date().toLocaleTimeString(),
        isMultiRoll: data.results.length > 1,
        total: data.total,
        modifier: data.modifier,
      };

      setRollHistory(prev => [newEntry, ...prev.slice(0, 19)]);
    });

    // Update stats
    const newCriticals = data.results.filter(r => r.result === DICE_CONFIGS[r.diceType]?.faces).length;
    const newFails = data.results.filter(r => r.result === 1).length;
    const totalResult = data.results.reduce((sum, r) => sum + r.result, 0);

    setStats(prev => ({
      totalRolls: prev.totalRolls + data.results.length,
      criticals: prev.criticals + newCriticals,
      critFails: prev.critFails + newFails,
      average: ((prev.average * prev.totalRolls + totalResult) / (prev.totalRolls + data.results.length)).toFixed(2),
    }));
  };

  // Quick roll presets
  const quickRolls = [
    { label: 'Attack (d20+5)', diceToRoll: [{ type: 'd20', count: 1 }], modifier: 5 },
    { label: '2d6 Damage', diceToRoll: [{ type: 'd6', count: 2 }], modifier: 0 },
    { label: 'Fireball (8d6)', diceToRoll: [{ type: 'd6', count: 8 }], modifier: 0 },
    { label: 'Sneak Attack (3d6)', diceToRoll: [{ type: 'd6', count: 3 }], modifier: 0 },
    { label: 'Great Weapon (2d6+4)', diceToRoll: [{ type: 'd6', count: 2 }], modifier: 4 },
    { label: 'Mixed (d20+d8+d6)', diceToRoll: [{ type: 'd20', count: 1 }, { type: 'd8', count: 1 }, { type: 'd6', count: 1 }], modifier: 0 },
  ];

  const openQuickRoll = (preset) => {
    setModalConfig({
      diceToRoll: preset.diceToRoll,
      modifier: preset.modifier,
      rollLabel: preset.label,
    });
    setModalOpen(true);
  };

  return (
    <div className="dice-test-page">
      <header className="dice-test-header">
        <h1>3D Dice Roller</h1>
        <p>WebGL-powered dice rolling with gold/amber styling</p>
      </header>

      <div className="dice-test-content">
        {/* Main Dice Roller */}
        <div className="dice-test-main">
          <DiceRoller3D
            ref={diceRollerRef}
            onRollComplete={handleRollComplete}
          />
        </div>

        <div className="dice-test-sidebar">
          {/* Trigger Examples Section */}
          <div className="triggers-panel">
            <h2>Embeddable Triggers</h2>
            <p className="panel-description">Click any trigger to open the dice roll modal</p>

            <div className="triggers-grid">
              {/* Different sizes */}
              <div className="trigger-group">
                <span className="trigger-label">Sizes:</span>
                <DiceTrigger
                  size="small"
                  diceType="d20"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd20', count: 1 }], modifier: 0, rollLabel: 'D20 Roll' });
                    setModalOpen(true);
                  }}
                />
                <DiceTrigger
                  size="medium"
                  diceType="d20"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd20', count: 1 }], modifier: 0, rollLabel: 'D20 Roll' });
                    setModalOpen(true);
                  }}
                />
                <DiceTrigger
                  size="large"
                  diceType="d20"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd20', count: 1 }], modifier: 0, rollLabel: 'D20 Roll' });
                    setModalOpen(true);
                  }}
                />
              </div>

              {/* Different variants */}
              <div className="trigger-group">
                <span className="trigger-label">Variants:</span>
                <DiceTrigger
                  variant="default"
                  diceType="d6"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd6', count: 1 }], modifier: 0, rollLabel: 'D6 Roll' });
                    setModalOpen(true);
                  }}
                />
                <DiceTrigger
                  variant="compact"
                  diceType="d6"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd6', count: 1 }], modifier: 0, rollLabel: 'D6 Roll' });
                    setModalOpen(true);
                  }}
                />
                <DiceTrigger
                  variant="icon-only"
                  diceType="d6"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd6', count: 1 }], modifier: 0, rollLabel: 'D6 Roll' });
                    setModalOpen(true);
                  }}
                />
              </div>

              {/* Multi-dice */}
              <div className="trigger-group">
                <span className="trigger-label">Multi:</span>
                <DiceTrigger
                  diceType="d6"
                  diceCount={2}
                  label="2d6"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd6', count: 2 }], modifier: 0, rollLabel: '2D6 Roll' });
                    setModalOpen(true);
                  }}
                />
                <DiceTrigger
                  diceType="d8"
                  diceCount={4}
                  label="4d8"
                  onClick={() => {
                    setModalConfig({ diceToRoll: [{ type: 'd8', count: 4 }], modifier: 0, rollLabel: '4D8 Roll' });
                    setModalOpen(true);
                  }}
                />
              </div>
            </div>
          </div>

          {/* Quick Rolls Section */}
          <div className="quick-rolls-panel">
            <h2>Quick Rolls</h2>
            <div className="quick-rolls-grid">
              {quickRolls.map((preset, index) => (
                <button
                  key={index}
                  className="quick-roll-btn"
                  onClick={() => openQuickRoll(preset)}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>

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
                    className={`history-item ${roll.isCritical ? 'critical' : ''} ${roll.isFail ? 'fail' : ''}`}
                  >
                    <span className="history-dice">{roll.diceType.toUpperCase()}</span>
                    <span className="history-result">{roll.result}</span>
                    {roll.isMultiRoll && roll.modifier !== undefined && (
                      <span className="history-total">
                        {roll.modifier !== 0 && `(+${roll.modifier})`}
                      </span>
                    )}
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
          <li>Gold/amber color scheme matching app style</li>
          <li>High-resolution 512px textures for crisp numbers</li>
          <li>Support for D4, D6, D8, D10, D12, D20</li>
          <li>Rolling number display during animation</li>
          <li>Multiple dice rolling simultaneously</li>
          <li>Embeddable trigger components</li>
          <li>Popup modal for dice rolls</li>
          <li>Roll modifiers support</li>
          <li>Critical hit/fail visual feedback</li>
          <li>Compact mode for embedded use</li>
        </ul>
      </div>

      {/* Dice Roll Modal */}
      <DiceRollModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        diceToRoll={modalConfig.diceToRoll}
        modifier={modalConfig.modifier}
        rollLabel={modalConfig.rollLabel}
        onRollComplete={handleModalRollComplete}
      />

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
          background: linear-gradient(135deg, #f59e0b, #d4a574);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          font-family: 'Cinzel', Georgia, serif;
        }

        .dice-test-header p {
          color: #888;
          margin: 0;
          font-size: 16px;
        }

        .dice-test-content {
          display: grid;
          grid-template-columns: 1fr 400px;
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

        .triggers-panel,
        .quick-rolls-panel,
        .stats-panel,
        .history-panel {
          background: rgba(26, 26, 46, 0.8);
          border: 1px solid rgba(212, 165, 116, 0.2);
          border-radius: 12px;
          padding: 20px;
        }

        .triggers-panel h2,
        .quick-rolls-panel h2,
        .stats-panel h2,
        .history-panel h2 {
          margin: 0 0 12px;
          font-size: 16px;
          color: #d4a574;
          font-family: 'Cinzel', Georgia, serif;
        }

        .panel-description {
          color: #666;
          font-size: 12px;
          margin: 0 0 16px;
        }

        .triggers-grid {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .trigger-group {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }

        .trigger-label {
          font-size: 12px;
          color: #888;
          min-width: 60px;
        }

        .quick-rolls-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 8px;
        }

        .quick-roll-btn {
          padding: 10px 12px;
          font-size: 12px;
          font-weight: 600;
          color: #e0e0e0;
          background: rgba(0, 0, 0, 0.3);
          border: 1px solid rgba(212, 165, 116, 0.2);
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          text-align: left;
        }

        .quick-roll-btn:hover {
          background: rgba(212, 165, 116, 0.15);
          border-color: rgba(212, 165, 116, 0.4);
          color: #fff;
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
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .stat-value {
          display: block;
          font-size: 28px;
          font-weight: bold;
          color: #ffffff;
          font-family: 'Cinzel', Georgia, serif;
        }

        .stat-label {
          display: block;
          font-size: 11px;
          color: #888;
          text-transform: uppercase;
          letter-spacing: 1px;
          margin-top: 4px;
        }

        .history-list {
          max-height: 300px;
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
          background: rgba(212, 165, 116, 0.1);
        }

        .history-item.critical {
          background: rgba(255, 215, 0, 0.12);
          border: 1px solid rgba(255, 215, 0, 0.25);
        }

        .history-item.fail {
          background: rgba(239, 68, 68, 0.12);
          border: 1px solid rgba(239, 68, 68, 0.25);
        }

        .history-dice {
          font-size: 11px;
          color: #d4a574;
          font-weight: bold;
          min-width: 35px;
        }

        .history-result {
          font-size: 20px;
          font-weight: bold;
          flex: 1;
          font-family: 'Cinzel', Georgia, serif;
        }

        .history-total {
          font-size: 12px;
          color: #8b5cf6;
        }

        .history-time {
          font-size: 10px;
          color: #666;
        }

        .features-section {
          max-width: 1400px;
          margin: 40px auto 0;
          background: rgba(26, 26, 46, 0.5);
          border: 1px solid rgba(212, 165, 116, 0.2);
          border-radius: 12px;
          padding: 20px;
        }

        .features-section h2 {
          margin: 0 0 16px;
          color: #d4a574;
          font-family: 'Cinzel', Georgia, serif;
        }

        .features-list {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 10px;
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .features-list li {
          padding: 8px 12px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 6px;
          font-size: 13px;
          color: #e0e0e0;
        }

        .features-list li::before {
          content: "\\2713 ";
          color: #10b981;
          font-weight: bold;
          margin-right: 8px;
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
          background: rgba(212, 165, 116, 0.4);
          border-radius: 3px;
        }

        .history-list::-webkit-scrollbar-thumb:hover {
          background: rgba(212, 165, 116, 0.6);
        }
      `}</style>
    </div>
  );
};

export default DiceRollerTest;
