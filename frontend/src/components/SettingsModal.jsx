import React, { forwardRef } from 'react';
import ControlPanel from './ControlPanel';

const SettingsModal = forwardRef(({ isOpen, onClose, ...props }, ref) => {
  return (
    <>
      {/* Always render ControlPanel but keep it hidden */}
      <div style={{ display: 'none' }}>
        <ControlPanel ref={ref} {...props} />
      </div>
      
      {/* Modal overlay - only show when isOpen */}
      {isOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-gaia-light rounded-lg shadow-lg p-6 w-full max-w-4xl">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-2xl font-bold text-white">Settings</h2>
              <button onClick={onClose} className="text-white text-2xl">&times;</button>
            </div>
            <ControlPanel {...props} />
          </div>
        </div>
      )}
    </>
  );
});

SettingsModal.displayName = 'SettingsModal';

export default SettingsModal;
