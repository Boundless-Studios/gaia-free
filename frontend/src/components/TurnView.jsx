import React from 'react';
import './TurnView.css';
import './ChatMessage.css';

const TurnView = ({ turn, className = '', showHeader = true, onPlayStop, isPlaying, onCopyToChat, turnInfo }) => {
  if (!turn) return null;

  let processedTurn = turn;
  let turnLines = [];

  // Handle different turn formats
  if (Array.isArray(turn)) {
    // turn is an array of player options
    turnLines = turn.filter(line => line && line.trim());
  } else if (typeof turn === 'string') {
    // If turn is a string that looks like JSON, try to parse it
    if (turn.trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(turn);
        // Convert the parsed object to a readable string
        if (typeof parsed === 'object') {
          processedTurn = Object.entries(parsed)
            .map(([key, value]) => `${key}: ${value}`)
            .join('\n');
        }
      } catch {
        // If parsing fails, keep it as a string
        processedTurn = turn;
      }
    }
    // Split string into lines
    turnLines = processedTurn.split('\n').filter(line => line.trim());
  }

  return (
    <div className={`turn-view base-view ${className}`}>
      {showHeader && (
        <div className="turn-header base-header">
          <h2 className="turn-title base-title">Player Options</h2>
        </div>
      )}
      {turn && (
        <div className="turn-content base-content">
          <div className="turn-text base-text">
            {turnLines.map((line, index) => (
              <div
                key={index}
                className="chat-message-container dm"
                onClick={() => onCopyToChat && onCopyToChat(line)}
                style={onCopyToChat ? { cursor: 'pointer' } : {}}
                title={onCopyToChat ? "Click to copy to chat input" : ""}
              >
                <div className="chat-message-content">
                  {line}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default TurnView;