import React, { useState } from 'react';
import { useRoom } from '../../contexts/RoomContext.jsx';
import RoomManagementDrawer from '../dm/RoomManagementDrawer.jsx';

/**
 * Room status display and management button for the header.
 * Shows Room/Campaign status and provides access to Room Management drawer.
 */
const RoomStatusBar = ({ campaignId }) => {
  const [showRoomDrawer, setShowRoomDrawer] = useState(false);

  // useRoom is always called - it returns null values when RoomProvider is not available
  const roomContext = useRoom();
  const { roomState } = roomContext || {};

  // Don't render if no room context or no campaign
  if (!roomContext || !campaignId) {
    return null;
  }

  const formatStatusLabel = (status) => {
    if (!status) return 'Unknown';
    return status.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const roomStatusColor = roomState?.room_status === 'active' ? 'text-green-400' : 'text-yellow-400';
  const campaignStatusColor = roomState?.campaign_status === 'active' ? 'text-green-400' : 'text-yellow-400';
  const roomStatusLabel = roomState?.room_status ? formatStatusLabel(roomState.room_status) : 'Waiting';
  const campaignStatusLabel = roomState?.campaign_status ? formatStatusLabel(roomState.campaign_status) : 'Setup';

  return (
    <>
      {/* Status labels */}
      <div className="flex items-center gap-2 text-xs">
        <span className="text-gray-400">Room:</span>
        <span className={roomStatusColor}>{roomStatusLabel}</span>
        <span className="text-gray-500">|</span>
        <span className="text-gray-400">Campaign:</span>
        <span className={campaignStatusColor}>{campaignStatusLabel}</span>
      </div>

      {/* Manage Room button */}
      <button
        onClick={() => setShowRoomDrawer(true)}
        className="px-3 py-1 bg-indigo-600 text-white rounded text-xs hover:bg-indigo-700 transition-colors font-medium"
      >
        Manage Room
      </button>

      {/* Room Management Drawer */}
      <RoomManagementDrawer
        campaignId={campaignId}
        isOpen={showRoomDrawer}
        onClose={() => setShowRoomDrawer(false)}
      />
    </>
  );
};

export default RoomStatusBar;
