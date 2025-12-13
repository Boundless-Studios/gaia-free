import React, { useState } from 'react';

/**
 * DiceTrigger - A small, embeddable button to initiate dice rolls
 *
 * Use this component to add dice rolling capabilities anywhere in the UI.
 * When clicked, it opens the DiceRollModal popup.
 *
 * @param {Object} props
 * @param {string} [props.diceType='d20'] - Default dice type
 * @param {number} [props.diceCount=1] - Number of dice to roll
 * @param {string} [props.label] - Optional label text
 * @param {string} [props.size='medium'] - Size: 'small', 'medium', 'large'
 * @param {string} [props.variant='default'] - Variant: 'default', 'compact', 'icon-only'
 * @param {Function} [props.onRollComplete] - Callback with roll results
 * @param {Function} [props.onClick] - Click handler (if you want to handle modal externally)
 * @param {boolean} [props.disabled] - Disable the trigger
 * @param {string} [props.className] - Additional CSS classes
 */
const DiceTrigger = ({
  diceType = 'd20',
  diceCount = 1,
  label,
  size = 'medium',
  variant = 'default',
  onRollComplete,
  onClick,
  disabled = false,
  className = '',
}) => {
  const [isHovered, setIsHovered] = useState(false);

  // Size configurations
  const sizeConfig = {
    small: {
      padding: '4px 8px',
      iconSize: '16px',
      fontSize: '11px',
      gap: '4px',
    },
    medium: {
      padding: '6px 12px',
      iconSize: '20px',
      fontSize: '13px',
      gap: '6px',
    },
    large: {
      padding: '10px 16px',
      iconSize: '24px',
      fontSize: '15px',
      gap: '8px',
    },
  };

  const config = sizeConfig[size] || sizeConfig.medium;

  const handleClick = (e) => {
    if (disabled) return;
    if (onClick) {
      onClick({ diceType, diceCount });
    }
  };

  // Generate display text
  const displayText = label || (diceCount > 1 ? `${diceCount}${diceType}` : diceType.toUpperCase());

  // D20 SVG icon
  const DiceIcon = () => (
    <svg
      width={config.iconSize}
      height={config.iconSize}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      {/* Icosahedron-like shape */}
      <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5" />
      <line x1="12" y1="2" x2="12" y2="22" />
      <line x1="2" y1="8.5" x2="22" y2="15.5" />
      <line x1="22" y1="8.5" x2="2" y2="15.5" />
    </svg>
  );

  return (
    <>
      <button
        className={`dice-trigger ${variant} ${size} ${className}`}
        onClick={handleClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        disabled={disabled}
        title={`Roll ${displayText}`}
        style={{
          '--trigger-padding': config.padding,
          '--trigger-gap': config.gap,
          '--trigger-font-size': config.fontSize,
        }}
      >
        <span className="dice-trigger-icon">
          <DiceIcon />
        </span>
        {variant !== 'icon-only' && (
          <span className="dice-trigger-label">{displayText}</span>
        )}
      </button>

      <style>{`
        .dice-trigger {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: var(--trigger-gap);
          padding: var(--trigger-padding);
          font-size: var(--trigger-font-size);
          font-weight: 600;
          color: #e0e0e0;
          background: linear-gradient(135deg, rgba(26, 26, 46, 0.9), rgba(15, 15, 26, 0.9));
          border: 1px solid rgba(212, 165, 116, 0.3);
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          font-family: inherit;
          white-space: nowrap;
        }

        .dice-trigger:hover:not(:disabled) {
          background: linear-gradient(135deg, rgba(212, 165, 116, 0.2), rgba(180, 130, 70, 0.15));
          border-color: rgba(212, 165, 116, 0.5);
          color: #ffffff;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(212, 165, 116, 0.2);
        }

        .dice-trigger:active:not(:disabled) {
          transform: translateY(0);
        }

        .dice-trigger:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .dice-trigger-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          color: #d4a574;
          transition: all 0.2s ease;
        }

        .dice-trigger:hover:not(:disabled) .dice-trigger-icon {
          color: #f59e0b;
          transform: rotate(15deg);
        }

        .dice-trigger-label {
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        /* Compact variant */
        .dice-trigger.compact {
          background: rgba(26, 26, 46, 0.7);
          border-color: rgba(212, 165, 116, 0.2);
        }

        .dice-trigger.compact:hover:not(:disabled) {
          background: rgba(212, 165, 116, 0.15);
        }

        /* Icon-only variant */
        .dice-trigger.icon-only {
          padding: 6px;
          border-radius: 50%;
          aspect-ratio: 1;
        }

        .dice-trigger.icon-only.small {
          padding: 4px;
        }

        .dice-trigger.icon-only.large {
          padding: 10px;
        }
      `}</style>
    </>
  );
};

export default DiceTrigger;
