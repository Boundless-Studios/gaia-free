import React from 'react';

const CampaignNameDisplay = ({ name }) => {
  if (!name) {
    return null;
  }

  return (
    <span className="text-xs text-gray-400 font-mono">
      Campaign: {name}
    </span>
  );
};

export default CampaignNameDisplay;
