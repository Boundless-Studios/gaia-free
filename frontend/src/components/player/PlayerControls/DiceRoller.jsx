import React, { useState } from 'react';

const DiceRoller = ({ onRoll, recentRolls = [] }) => {
  const [selectedDie, setSelectedDie] = useState('d20');
  const [modifier, setModifier] = useState(0);
  const [numDice, setNumDice] = useState(1);
  const [advantage, setAdvantage] = useState('normal');

  // Available dice types - reduced to 4 most common
  const diceTypes = [
    { value: 'd6', label: 'D6', icon: '⚀' },
    { value: 'd8', label: 'D8', icon: '🎲' },
    { value: 'd20', label: 'D20', icon: '🎱' },
    { value: 'd100', label: 'D100', icon: '💯' }
  ];

  // Roll dice logic
  const rollDice = () => {
    const dieValue = parseInt(selectedDie.substring(1));
    const rolls = [];
    let total = 0;

    // Handle advantage/disadvantage for d20
    if (selectedDie === 'd20' && advantage !== 'normal') {
      const roll1 = Math.floor(Math.random() * 20) + 1;
      const roll2 = Math.floor(Math.random() * 20) + 1;

      if (advantage === 'advantage') {
        rolls.push(Math.max(roll1, roll2));
        total = Math.max(roll1, roll2);
      } else {
        rolls.push(Math.min(roll1, roll2));
        total = Math.min(roll1, roll2);
      }
    } else {
      // Regular rolls
      for (let i = 0; i < numDice; i++) {
        const roll = Math.floor(Math.random() * dieValue) + 1;
        rolls.push(roll);
        total += roll;
      }
    }

    const finalTotal = total + modifier;

    const rollResult = {
      dice: selectedDie,
      numDice,
      rolls,
      modifier,
      advantage,
      total: finalTotal,
      expression: buildExpression()
    };

    if (onRoll) {
      onRoll(rollResult);
    }
  };

  // Build expression string
  const buildExpression = () => {
    let expr = `${numDice}${selectedDie}`;
    if (advantage === 'advantage') expr += ' (advantage)';
    if (advantage === 'disadvantage') expr += ' (disadvantage)';
    if (modifier > 0) expr += ` + ${modifier}`;
    if (modifier < 0) expr += ` - ${Math.abs(modifier)}`;
    return expr;
  };

  // Format roll result for display
  const formatRollResult = (roll) => {
    const rollsStr = roll.rolls.join(', ');
    return `${roll.expression} = [${rollsStr}] ${roll.modifier !== 0 ? `${roll.modifier > 0 ? '+' : ''}${roll.modifier}` : ''} = ${roll.total}`;
  };

  return (
    <div className="dice-roller">
      {/* Header */}
      <h3 className="section-title">
        <span className="section-icon">🎲</span>
        Roll Dice
      </h3>

      {/* 3-Column Horizontal Layout */}
      <div className="dice-three-column">

        {/* Left Column: Dice Selection (2x2 Grid) */}
        <div className="dice-column-left">
          <div className="dice-grid-2x2">
            {diceTypes.map(die => (
              <button
                key={die.value}
                className={`die-btn ${selectedDie === die.value ? 'selected' : ''}`}
                onClick={() => setSelectedDie(die.value)}
                title={die.label}
              >
                <span className="die-icon">{die.icon}</span>
                <span className="die-label">{die.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Middle Column: Controls */}
        <div className="dice-column-middle">
          {/* Count, Modifier inputs, and Roll button */}
          <div className="input-row">
            <div className="input-group">
              <label>Count</label>
              <input
                type="number"
                min="1"
                max="10"
                value={numDice}
                onChange={(e) => setNumDice(parseInt(e.target.value) || 1)}
                className="dice-input"
              />
            </div>
            <div className="input-group">
              <label>Modifier</label>
              <input
                type="number"
                min="-99"
                max="99"
                value={modifier}
                onChange={(e) => setModifier(parseInt(e.target.value) || 0)}
                className="dice-input"
              />
            </div>
            <button className="roll-btn-main" onClick={rollDice}>
              🎲 Roll
            </button>
          </div>

          {/* Advantage Controls (D20 only) */}
          {selectedDie === 'd20' && (
            <div className="advantage-controls">
              <button
                className={`adv-btn ${advantage === 'disadvantage' ? 'active' : ''}`}
                onClick={() => setAdvantage('disadvantage')}
              >
                📉 Disadvantage
              </button>
              <button
                className={`adv-btn ${advantage === 'normal' ? 'active' : ''}`}
                onClick={() => setAdvantage('normal')}
              >
                ⚖️ Normal
              </button>
              <button
                className={`adv-btn ${advantage === 'advantage' ? 'active' : ''}`}
                onClick={() => setAdvantage('advantage')}
              >
                📈 Advantage
              </button>
            </div>
          )}

          {/* Recent Result */}
          {recentRolls.length > 0 && (
            <div className="roll-result-display">
              {formatRollResult(recentRolls[0])}
            </div>
          )}
        </div>

        {/* Right Column: Quick Actions (Vertical) */}
        <div className="dice-column-right">
          <div className="quick-actions-vertical">
            <button
              className="quick-btn"
              onClick={() => {
                setSelectedDie('d20');
                setNumDice(1);
                setModifier(0);
                setAdvantage('normal');
                setTimeout(rollDice, 100);
              }}
            >
              🎯 Attack
            </button>
            <button
              className="quick-btn"
              onClick={() => {
                setSelectedDie('d20');
                setNumDice(1);
                setModifier(0);
                setAdvantage('normal');
                setTimeout(rollDice, 100);
              }}
            >
              💪 Check
            </button>
            <button
              className="quick-btn"
              onClick={() => {
                setSelectedDie('d20');
                setNumDice(1);
                setModifier(0);
                setAdvantage('normal');
                setTimeout(rollDice, 100);
              }}
            >
              🛡️ Save
            </button>
            <button
              className="quick-btn"
              onClick={() => {
                setSelectedDie('d20');
                setNumDice(1);
                setModifier(0);
                setAdvantage('normal');
                setTimeout(rollDice, 100);
              }}
            >
              ⚡ Initiative
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};

export default DiceRoller;