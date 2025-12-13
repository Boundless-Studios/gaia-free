import React, { forwardRef, useState } from 'react';
import ControlPanel from './ControlPanel';
import GameSettingsPanel from './GameSettingsPanel';

const SettingsModal = forwardRef(({ isOpen, onClose, campaignId, ...props }, ref) => {
  const [activeSection, setActiveSection] = useState('audio');

  return (
    <>
      {/* Always render ControlPanel but keep it hidden */}
      <div style={{ display: 'none' }}>
        <ControlPanel ref={ref} campaignId={campaignId} {...props} />
      </div>

      {/* Modal overlay - only show when isOpen */}
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-gaia-light rounded-lg shadow-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
            {/* Header */}
            <div className="flex justify-between items-center p-6 pb-4 border-b border-gray-700">
              <h2 className="text-2xl font-bold text-white">Settings</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl transition-colors">&times;</button>
            </div>

            {/* Tab Navigation */}
            <div className="flex border-b border-gray-700 px-6">
              <button
                className={`px-4 py-3 text-sm font-medium transition-colors ${
                  activeSection === 'audio'
                    ? 'text-gaia-accent border-b-2 border-gaia-accent -mb-px'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
                onClick={() => setActiveSection('audio')}
              >
                Audio & Voice
              </button>
              <button
                className={`px-4 py-3 text-sm font-medium transition-colors ${
                  activeSection === 'game'
                    ? 'text-gaia-accent border-b-2 border-gaia-accent -mb-px'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
                onClick={() => setActiveSection('game')}
              >
                Game Preferences
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
              {activeSection === 'audio' && (
                <ControlPanel campaignId={campaignId} {...props} />
              )}
              {activeSection === 'game' && (
                <GameSettingsPanel campaignId={campaignId} />
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
});

SettingsModal.displayName = 'SettingsModal';

export default SettingsModal;
