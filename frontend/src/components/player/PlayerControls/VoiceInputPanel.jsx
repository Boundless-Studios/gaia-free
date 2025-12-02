import React, { useState, useRef } from 'react';

const VoiceInputPanel = ({
  onVoiceSubmit,
  isTranscribing = false,
  voiceActivityLevel = 0,
  playerOptions = null,
  onPlayerOption = null
}) => {
  const [inputText, setInputText] = useState('');
  const textareaRef = useRef(null);

  // Handle text submission
  const handleSubmit = () => {
    if (inputText.trim() && onVoiceSubmit) {
      onVoiceSubmit(inputText.trim());
      setInputText('');
    }
  };

  // Handle Enter key (with Shift+Enter for new lines)
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="voice-input-panel">
      {/* Text Input Area */}
      <div className="text-input-area">
        <textarea
          ref={textareaRef}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your action..."
          className="voice-textarea"
          rows={2}
        />

        {/* Input Controls */}
        <div className="input-controls">
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={!inputText.trim()}
            title="Send message"
          >
            📤 Send
          </button>
        </div>
      </div>

      {/* Player Options (if available) */}
      {playerOptions && (
        <div className="player-options-sidebar">
          {Array.isArray(playerOptions) ? (
            playerOptions.map((option, index) => (
              <button
                key={index}
                className="quick-action-btn player-option-btn"
                onClick={() => {
                  if (onPlayerOption) {
                    onPlayerOption(option);
                  }
                }}
              >
                {option}
              </button>
            ))
          ) : (
            <button
              className="quick-action-btn player-option-btn"
              onClick={() => {
                if (onPlayerOption) {
                  onPlayerOption(playerOptions);
                }
              }}
            >
              {playerOptions}
            </button>
          )}
        </div>
      )}

      {/* Basic Actions */}
      <div className="quick-actions-sidebar">
        <button
          className="quick-action-btn"
          onClick={() => setInputText('I want to investigate the area.')}
        >
          🔍 Investigate
        </button>
        <button
          className="quick-action-btn"
          onClick={() => setInputText('I want to attack.')}
        >
          ⚔️ Attack
        </button>
        <button
          className="quick-action-btn"
          onClick={() => setInputText('I want to cast a spell.')}
        >
          ✨ Cast Spell
        </button>
        <button
          className="quick-action-btn"
          onClick={() => setInputText('I want to help my allies.')}
        >
          🤝 Help
        </button>
      </div>
    </div>
  );
};

export default VoiceInputPanel;