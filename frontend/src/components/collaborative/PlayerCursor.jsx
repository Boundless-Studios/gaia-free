import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import './PlayerCursor.css';

/**
 * PlayerCursor - Renders a cursor indicator for another player in the collaborative editor
 *
 * Calculates position based on character offset and displays:
 * - Vertical cursor line
 * - Player name label
 * - Color-coded styling
 *
 * @param {object} cursor - Cursor data { playerId, characterName, position, color }
 * @param {object} textareaRef - Reference to the textarea element
 */
const PlayerCursor = ({ cursor, textareaRef }) => {
  const [cursorStyle, setCursorStyle] = useState({});

  useEffect(() => {
    if (!textareaRef.current) return;

    const textarea = textareaRef.current;
    const text = textarea.value;
    const position = Math.min(cursor.position, text.length);

    // Create a temporary span to measure cursor position
    const measureDiv = document.createElement('div');
    measureDiv.style.cssText = `
      position: absolute;
      visibility: hidden;
      white-space: pre-wrap;
      word-wrap: break-word;
      font-family: ${window.getComputedStyle(textarea).fontFamily};
      font-size: ${window.getComputedStyle(textarea).fontSize};
      line-height: ${window.getComputedStyle(textarea).lineHeight};
      padding: ${window.getComputedStyle(textarea).padding};
      width: ${textarea.clientWidth}px;
    `;

    const textBeforeCursor = text.substring(0, position);
    measureDiv.textContent = textBeforeCursor;
    document.body.appendChild(measureDiv);

    // Calculate cursor position
    const lines = textBeforeCursor.split('\n');
    const lineNumber = lines.length - 1;
    const lineHeight = parseInt(window.getComputedStyle(textarea).lineHeight);
    const paddingTop = parseInt(window.getComputedStyle(textarea).paddingTop);

    // Approximate horizontal position (simplified)
    const lastLine = lines[lines.length - 1];
    const charWidth = parseInt(window.getComputedStyle(textarea).fontSize) * 0.6; // Approximate
    const left = lastLine.length * charWidth + parseInt(window.getComputedStyle(textarea).paddingLeft);
    const top = lineNumber * lineHeight + paddingTop;

    document.body.removeChild(measureDiv);

    setCursorStyle({
      left: `${Math.min(left, textarea.clientWidth - 20)}px`,
      top: `${top}px`,
      height: `${lineHeight}px`,
      borderColor: cursor.color
    });
  }, [cursor.position, cursor.color, textareaRef]);

  return (
    <div className="player-cursor" style={cursorStyle}>
      <div className="cursor-line" style={{ backgroundColor: cursor.color }} />
      <div
        className="cursor-label"
        style={{
          backgroundColor: cursor.color,
          color: '#fff'
        }}
      >
        {cursor.characterName}
      </div>
    </div>
  );
};

PlayerCursor.propTypes = {
  cursor: PropTypes.shape({
    playerId: PropTypes.string.isRequired,
    characterName: PropTypes.string.isRequired,
    position: PropTypes.number.isRequired,
    color: PropTypes.string.isRequired,
    isActivePlayer: PropTypes.bool
  }).isRequired,
  textareaRef: PropTypes.object.isRequired
};

export default PlayerCursor;
