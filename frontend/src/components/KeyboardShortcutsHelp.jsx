import React, { useMemo } from 'react';
import { Modal } from './base-ui/Modal';
import './KeyboardShortcutsHelp.css';

const KeyboardShortcutsHelp = ({ isOpen, onClose }) => {
  // Detect Mac platform to show "Option" instead of "Alt"
  const isMac = useMemo(() =>
    /Mac|iPhone|iPod|iPad/.test(navigator.platform),
    []
  );

  const altKey = isMac ? 'Option' : 'Alt';

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="⌨️ Keyboard Shortcuts"
      width="max-w-md"
    >
      <div className="shortcuts-list">
        <div className="shortcut-item">
          <span className="shortcut-keys">Ctrl + G</span>
          <span className="shortcut-description">Generate image from selected text</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">Ctrl + /</span>
          <span className="shortcut-description">Start/stop audio transcription</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">{altKey} + S</span>
          <span className="shortcut-description">Generate scene image</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">{altKey} + C</span>
          <span className="shortcut-description">Generate character image</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">{altKey} + I</span>
          <span className="shortcut-description">Generate item image</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">{altKey} + B</span>
          <span className="shortcut-description">Generate beast image</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">{altKey} + M</span>
          <span className="shortcut-description">Generate moment image</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">1 - 8</span>
          <span className="shortcut-description">Select voice and play selected text</span>
        </div>

        <div className="shortcut-item">
          <span className="shortcut-keys">9</span>
          <span className="shortcut-description">Generate sound effect from selected text</span>
        </div>

        <div className="shortcut-note">
          <p>💡 Tip: Select any text in the narrative, then use these shortcuts for quick actions!</p>
        </div>
      </div>
    </Modal>
  );
};

export default KeyboardShortcutsHelp;