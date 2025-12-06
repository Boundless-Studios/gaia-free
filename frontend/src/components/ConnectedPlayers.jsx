import React, { useState, useEffect } from 'react';
import apiService from '../services/apiService';

const ConnectedPlayers = ({ campaignId, dmSocket }) => {
  const [connectedPlayers, setConnectedPlayers] = useState([]);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (!campaignId) {
      setConnectedPlayers([]);
      return;
    }

    const fetchConnectedPlayers = async () => {
      try {
        const data = await apiService.getConnectedPlayers(campaignId);
        if (data && data.success) {
          setConnectedPlayers(data.connected_players || []);
        }
      } catch (error) {
        // Gracefully handle 429 plain-text or network errors
        console.debug('Connected players fetch temporarily unavailable');
      }
    };

    // Initial fetch
    fetchConnectedPlayers();

    // Listen for Socket.IO events
    const handlePlayerConnected = () => fetchConnectedPlayers();
    const handlePlayerDisconnected = () => fetchConnectedPlayers();

    if (dmSocket) {
      dmSocket.on('player_connected', handlePlayerConnected);
      dmSocket.on('player_disconnected', handlePlayerDisconnected);
    }

    // Poll every 30 seconds as backup
    const interval = setInterval(fetchConnectedPlayers, 30000);

    return () => {
      clearInterval(interval);
      if (dmSocket) {
        dmSocket.off('player_connected', handlePlayerConnected);
        dmSocket.off('player_disconnected', handlePlayerDisconnected);
      }
    };
  }, [campaignId, dmSocket]);

  if (!campaignId || connectedPlayers.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1 px-2 py-1 bg-gaia-light border border-gaia-border rounded text-xs text-gaia-text hover:bg-gaia-border transition-colors"
        title="Connected players"
      >
        <span className="text-green-500">●</span>
        <span>{connectedPlayers.length} player{connectedPlayers.length !== 1 ? 's' : ''}</span>
        <svg
          className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <div className="absolute top-full right-0 mt-1 w-64 bg-gaia-light border border-gaia-border rounded-lg shadow-lg z-50">
          <div className="p-2 border-b border-gaia-border">
            <h4 className="text-xs font-semibold text-gaia-text">Connected Players</h4>
          </div>
          <div className="max-h-48 overflow-y-auto">
            {connectedPlayers.map((player, index) => (
              <div
                key={index}
                className="p-2 border-b border-gaia-border last:border-b-0 hover:bg-gaia-border transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-green-500 text-xs">●</span>
                    <span className="text-xs text-gaia-text">
                      {player.display_name || player.user_id || 'Anonymous'}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(player.connected_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConnectedPlayers;
