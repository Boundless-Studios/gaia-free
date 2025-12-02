import React from 'react';

const SettingsButton = ({ onClick }) => {
  return (
    <button onClick={onClick} className="px-3 py-1 bg-gray-700 text-white rounded text-xs hover:bg-gray-800 transition-colors font-medium">
      ⚙️ Settings
    </button>
  );
};

export default SettingsButton;
