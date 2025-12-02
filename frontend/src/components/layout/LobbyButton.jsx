import React from 'react';
import { Link } from 'react-router-dom';

const LobbyButton = () => {
  return (
    <Link
      to="/"
      className="px-3 py-1 bg-purple-500 text-white rounded text-xs hover:bg-purple-600 transition-colors font-medium"
    >
      Lobby
    </Link>
  );
};

export default LobbyButton;
