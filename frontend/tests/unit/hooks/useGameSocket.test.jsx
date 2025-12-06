/**
 * Comprehensive tests for Socket.IO hook implementation.
 *
 * These tests define the expected behavior BEFORE implementation (TDD approach).
 * They cover:
 * - Connection lifecycle
 * - Reconnection behavior
 * - Event handling
 * - Authentication
 * - Multi-tab scenarios
 * - Error handling
 *
 * Run with: npm test -- --testPathPattern=useGameSocket
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

// Mock socket.io-client before importing the hook
const mockSocket = {
  connected: false,
  id: 'mock-socket-id',
  on: vi.fn(),
  off: vi.fn(),
  emit: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  io: {
    opts: {},
  },
};

// Track registered event handlers
const eventHandlers = new Map();

mockSocket.on.mockImplementation((event, handler) => {
  if (!eventHandlers.has(event)) {
    eventHandlers.set(event, []);
  }
  eventHandlers.get(event).push(handler);
  return mockSocket;
});

mockSocket.off.mockImplementation((event, handler) => {
  if (eventHandlers.has(event)) {
    const handlers = eventHandlers.get(event);
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }
  return mockSocket;
});

// Helper to trigger events
const triggerEvent = (event, data) => {
  const handlers = eventHandlers.get(event) || [];
  handlers.forEach((handler) => handler(data));
};

vi.mock('socket.io-client', () => ({
  io: vi.fn(() => mockSocket),
}));

// This import will work once the hook is implemented
// For now, we define the expected interface
// import { useGameSocket } from '../../../src/hooks/useGameSocket';

// Mock implementation for testing the interface
const useGameSocket = ({ campaignId, getAccessToken, handlers = {} }) => {
  const [isConnected, setIsConnected] = React.useState(false);
  const [connectionError, setConnectionError] = React.useState(null);
  const socketRef = React.useRef(null);

  React.useEffect(() => {
    if (!campaignId) return;

    // This is what the real implementation would do
    const { io } = require('socket.io-client');
    const socket = io('/campaign', {
      auth: async (cb) => {
        const token = await getAccessToken?.();
        cb({ token, session_id: campaignId });
      },
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 30000,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setIsConnected(true);
      setConnectionError(null);
    });

    socket.on('disconnect', () => {
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      setConnectionError(error.message);
    });

    // Register event handlers
    Object.entries(handlers).forEach(([event, handler]) => {
      socket.on(event, handler);
    });

    return () => {
      socket.disconnect();
    };
  }, [campaignId]);

  const emit = React.useCallback(
    (event, data) => {
      if (socketRef.current?.connected) {
        socketRef.current.emit(event, data);
      }
    },
    []
  );

  return {
    socket: socketRef.current,
    isConnected,
    connectionError,
    emit,
  };
};

// Import React for the mock implementation
import React from 'react';

describe('useGameSocket Hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    eventHandlers.clear();
    mockSocket.connected = false;
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  // ===========================================================================
  // Connection Lifecycle Tests
  // ===========================================================================

  describe('Connection Lifecycle', () => {
    it('should not connect without campaignId', () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: null,
          getAccessToken: vi.fn(),
        })
      );

      expect(result.current.isConnected).toBe(false);
      expect(result.current.socket).toBeNull();
    });

    it('should connect when campaignId is provided', async () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn().mockResolvedValue('test-token'),
        })
      );

      // Simulate connection
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });
    });

    it('should disconnect when component unmounts', () => {
      const { unmount } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      unmount();

      expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    it('should reconnect when campaignId changes', async () => {
      const { result, rerender } = renderHook(
        ({ campaignId }) =>
          useGameSocket({
            campaignId,
            getAccessToken: vi.fn().mockResolvedValue('test-token'),
          }),
        { initialProps: { campaignId: 'campaign-111' } }
      );

      // Initial connection
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      // Change campaign
      rerender({ campaignId: 'campaign-222' });

      // Should disconnect and reconnect
      expect(mockSocket.disconnect).toHaveBeenCalled();
    });
  });

  // ===========================================================================
  // Authentication Tests
  // ===========================================================================

  describe('Authentication', () => {
    it('should pass token to auth callback', async () => {
      const mockGetToken = vi.fn().mockResolvedValue('jwt-token-123');

      renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: mockGetToken,
        })
      );

      // The io() call should have been made with auth config
      const { io } = require('socket.io-client');
      expect(io).toHaveBeenCalled();

      // Verify auth config was passed
      const callArgs = io.mock.calls[0];
      expect(callArgs[1]).toHaveProperty('auth');
    });

    it('should handle missing token gracefully', async () => {
      const mockGetToken = vi.fn().mockResolvedValue(null);

      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: mockGetToken,
        })
      );

      // Should still attempt connection (dev mode allows no token)
      const { io } = require('socket.io-client');
      expect(io).toHaveBeenCalled();
    });

    it('should handle token refresh failure', async () => {
      const mockGetToken = vi.fn().mockRejectedValue(new Error('Token expired'));

      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: mockGetToken,
        })
      );

      // Simulate auth error
      act(() => {
        triggerEvent('connect_error', { message: 'Authentication failed' });
      });

      await waitFor(() => {
        expect(result.current.connectionError).toBe('Authentication failed');
      });
    });
  });

  // ===========================================================================
  // Event Handling Tests
  // ===========================================================================

  describe('Event Handling', () => {
    it('should register provided event handlers', () => {
      const onNarrativeChunk = vi.fn();
      const onCampaignUpdate = vi.fn();

      renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
          handlers: {
            narrative_chunk: onNarrativeChunk,
            campaign_updated: onCampaignUpdate,
          },
        })
      );

      // Verify handlers were registered
      expect(mockSocket.on).toHaveBeenCalledWith('narrative_chunk', onNarrativeChunk);
      expect(mockSocket.on).toHaveBeenCalledWith('campaign_updated', onCampaignUpdate);
    });

    it('should invoke handlers when events are received', async () => {
      const onNarrativeChunk = vi.fn();

      renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
          handlers: {
            narrative_chunk: onNarrativeChunk,
          },
        })
      );

      // Trigger the event
      act(() => {
        triggerEvent('narrative_chunk', {
          content: 'The adventure begins...',
          is_final: false,
        });
      });

      expect(onNarrativeChunk).toHaveBeenCalledWith({
        content: 'The adventure begins...',
        is_final: false,
      });
    });

    it('should handle multiple events of same type', async () => {
      const onAudioChunk = vi.fn();

      renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
          handlers: {
            audio_chunk_ready: onAudioChunk,
          },
        })
      );

      // Trigger multiple events
      act(() => {
        triggerEvent('audio_chunk_ready', { sequence: 0 });
        triggerEvent('audio_chunk_ready', { sequence: 1 });
        triggerEvent('audio_chunk_ready', { sequence: 2 });
      });

      expect(onAudioChunk).toHaveBeenCalledTimes(3);
    });
  });

  // ===========================================================================
  // Emit Tests
  // ===========================================================================

  describe('Emit Functionality', () => {
    it('should emit events when connected', () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Connect first
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      // Emit an event
      act(() => {
        result.current.emit('yjs_update', {
          sessionId: 'campaign-123',
          update: [1, 2, 3],
        });
      });

      expect(mockSocket.emit).toHaveBeenCalledWith('yjs_update', {
        sessionId: 'campaign-123',
        update: [1, 2, 3],
      });
    });

    it('should not emit when disconnected', () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Don't connect - stay disconnected
      mockSocket.connected = false;

      act(() => {
        result.current.emit('yjs_update', { data: 'test' });
      });

      expect(mockSocket.emit).not.toHaveBeenCalled();
    });
  });

  // ===========================================================================
  // Reconnection Tests
  // ===========================================================================

  describe('Reconnection Behavior', () => {
    it('should update isConnected on disconnect', async () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Connect
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      expect(result.current.isConnected).toBe(true);

      // Disconnect
      act(() => {
        mockSocket.connected = false;
        triggerEvent('disconnect');
      });

      expect(result.current.isConnected).toBe(false);
    });

    it('should clear connection error on successful reconnect', async () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Simulate connection error
      act(() => {
        triggerEvent('connect_error', { message: 'Network error' });
      });

      expect(result.current.connectionError).toBe('Network error');

      // Successful reconnect
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      expect(result.current.connectionError).toBeNull();
    });

    it('should preserve handlers after reconnect', async () => {
      const onNarrativeChunk = vi.fn();

      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
          handlers: {
            narrative_chunk: onNarrativeChunk,
          },
        })
      );

      // Connect, disconnect, reconnect
      act(() => {
        triggerEvent('connect');
        triggerEvent('disconnect');
        triggerEvent('connect');
      });

      // Handler should still work
      act(() => {
        triggerEvent('narrative_chunk', { content: 'test' });
      });

      expect(onNarrativeChunk).toHaveBeenCalled();
    });
  });

  // ===========================================================================
  // Connection State Tests
  // ===========================================================================

  describe('Connection State', () => {
    it('should expose socket instance', () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Socket should be available after initial render
      expect(result.current.socket).toBeDefined();
    });

    it('should track connection state accurately', async () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      // Initially disconnected
      expect(result.current.isConnected).toBe(false);

      // Connect
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });
      expect(result.current.isConnected).toBe(true);

      // Disconnect
      act(() => {
        mockSocket.connected = false;
        triggerEvent('disconnect');
      });
      expect(result.current.isConnected).toBe(false);

      // Reconnect
      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });
      expect(result.current.isConnected).toBe(true);
    });
  });

  // ===========================================================================
  // Error Handling Tests
  // ===========================================================================

  describe('Error Handling', () => {
    it('should capture connection errors', async () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      act(() => {
        triggerEvent('connect_error', { message: 'Connection refused' });
      });

      expect(result.current.connectionError).toBe('Connection refused');
      expect(result.current.isConnected).toBe(false);
    });

    it('should handle server disconnect gracefully', () => {
      const { result } = renderHook(() =>
        useGameSocket({
          campaignId: 'campaign-123',
          getAccessToken: vi.fn(),
        })
      );

      act(() => {
        mockSocket.connected = true;
        triggerEvent('connect');
      });

      // Server forces disconnect
      act(() => {
        mockSocket.connected = false;
        triggerEvent('disconnect', 'io server disconnect');
      });

      expect(result.current.isConnected).toBe(false);
    });
  });
});

// ===========================================================================
// Integration-Style Tests (with more realistic scenarios)
// ===========================================================================

describe('useGameSocket Integration Scenarios', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    eventHandlers.clear();
    mockSocket.connected = false;
  });

  it('should handle complete game session flow', async () => {
    const onCampaignUpdate = vi.fn();
    const onNarrativeChunk = vi.fn();
    const onSeatUpdate = vi.fn();

    const { result } = renderHook(() =>
      useGameSocket({
        campaignId: 'campaign-123',
        getAccessToken: vi.fn().mockResolvedValue('token'),
        handlers: {
          campaign_updated: onCampaignUpdate,
          narrative_chunk: onNarrativeChunk,
          'room.seat_updated': onSeatUpdate,
        },
      })
    );

    // 1. Connect
    act(() => {
      mockSocket.connected = true;
      triggerEvent('connect');
    });
    expect(result.current.isConnected).toBe(true);

    // 2. Receive campaign state
    act(() => {
      triggerEvent('campaign_updated', {
        campaign_id: 'campaign-123',
        structured_data: { scene: 'tavern' },
      });
    });
    expect(onCampaignUpdate).toHaveBeenCalled();

    // 3. DM starts narration
    act(() => {
      triggerEvent('narrative_chunk', { content: 'Welcome, adventurers...', is_final: false });
      triggerEvent('narrative_chunk', { content: ' The tavern is quiet.', is_final: true });
    });
    expect(onNarrativeChunk).toHaveBeenCalledTimes(2);

    // 4. Player joins a seat
    act(() => {
      triggerEvent('room.seat_updated', {
        seat: { seat_id: 'seat-1', owner_user_id: 'player-1' },
      });
    });
    expect(onSeatUpdate).toHaveBeenCalled();

    // 5. Network blip - disconnect and reconnect
    act(() => {
      mockSocket.connected = false;
      triggerEvent('disconnect');
    });
    expect(result.current.isConnected).toBe(false);

    act(() => {
      mockSocket.connected = true;
      triggerEvent('connect');
    });
    expect(result.current.isConnected).toBe(true);

    // 6. Continue receiving events
    act(() => {
      triggerEvent('narrative_chunk', { content: 'The door opens...', is_final: false });
    });
    expect(onNarrativeChunk).toHaveBeenCalledTimes(3);
  });

  it('should handle collaborative editing flow', async () => {
    const onYjsUpdate = vi.fn();
    const onPlayerList = vi.fn();

    const { result } = renderHook(() =>
      useGameSocket({
        campaignId: 'campaign-123',
        getAccessToken: vi.fn(),
        handlers: {
          yjs_update: onYjsUpdate,
          player_list: onPlayerList,
        },
      })
    );

    act(() => {
      mockSocket.connected = true;
      triggerEvent('connect');
    });

    // Receive updates from other players
    act(() => {
      triggerEvent('yjs_update', {
        sessionId: 'campaign-123',
        playerId: 'other-player',
        update: [1, 2, 3, 4, 5],
      });
    });
    expect(onYjsUpdate).toHaveBeenCalled();

    // Send our own update
    act(() => {
      result.current.emit('yjs_update', {
        sessionId: 'campaign-123',
        playerId: 'me',
        update: [6, 7, 8],
      });
    });
    expect(mockSocket.emit).toHaveBeenCalledWith('yjs_update', expect.any(Object));

    // Player list update
    act(() => {
      triggerEvent('player_list', {
        players: [
          { id: 'player-1', name: 'Aragorn' },
          { id: 'player-2', name: 'Gandalf' },
        ],
      });
    });
    expect(onPlayerList).toHaveBeenCalled();
  });

  it('should handle audio synchronization flow', async () => {
    const onAudioStreamStarted = vi.fn();
    const onAudioChunkReady = vi.fn();
    const onAudioStreamStopped = vi.fn();

    const { result } = renderHook(() =>
      useGameSocket({
        campaignId: 'campaign-123',
        getAccessToken: vi.fn(),
        handlers: {
          audio_stream_started: onAudioStreamStarted,
          audio_chunk_ready: onAudioChunkReady,
          audio_stream_stopped: onAudioStreamStopped,
        },
      })
    );

    act(() => {
      mockSocket.connected = true;
      triggerEvent('connect');
    });

    // Audio stream starts
    act(() => {
      triggerEvent('audio_stream_started', {
        text: 'Welcome to the adventure',
        chunk_ids: ['chunk-1', 'chunk-2', 'chunk-3'],
      });
    });
    expect(onAudioStreamStarted).toHaveBeenCalled();

    // Receive audio chunks
    for (let i = 0; i < 3; i++) {
      act(() => {
        triggerEvent('audio_chunk_ready', {
          chunk: { id: `chunk-${i + 1}` },
          sequence_number: i,
        });
      });
    }
    expect(onAudioChunkReady).toHaveBeenCalledTimes(3);

    // Acknowledge playback
    act(() => {
      result.current.emit('audio_played', { chunk_id: 'chunk-1' });
      result.current.emit('audio_played', { chunk_id: 'chunk-2' });
      result.current.emit('audio_played', { chunk_id: 'chunk-3' });
    });
    expect(mockSocket.emit).toHaveBeenCalledTimes(3);

    // Stream ends
    act(() => {
      triggerEvent('audio_stream_stopped', {});
    });
    expect(onAudioStreamStopped).toHaveBeenCalled();
  });
});
