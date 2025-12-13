/**
 * Unit tests for useTurnBasedMessages hook.
 *
 * Tests cover:
 * - Basic turn management
 * - History loading and merge behavior
 * - latestTurnRef monotonicity (never regresses)
 * - History vs WebSocket data reconciliation
 * - Streaming state management
 *
 * Run with: npm test -- --testPathPattern=useTurnBasedMessages
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { useTurnBasedMessages } from '../../../src/hooks/useTurnBasedMessages';

describe('useTurnBasedMessages Hook', () => {
  beforeEach(() => {
    // Reset any state between tests
  });

  // ===========================================================================
  // Basic Turn Management
  // ===========================================================================

  describe('Basic Turn Management', () => {
    it('should initialize with empty state', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      expect(result.current.turns).toEqual([]);
      expect(result.current.turnsByNumber).toEqual({});
      expect(result.current.processingTurn).toBeNull();
      expect(result.current.currentTurnNumber).toBe(0);
      expect(result.current.isProcessing).toBe(false);
    });

    it('should handle turn_started event', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnStarted({
          turn_number: 1,
          session_id: 'campaign-123',
        });
      });

      expect(result.current.processingTurn).toBe(1);
      expect(result.current.isProcessing).toBe(true);
      expect(result.current.turnsByNumber[1]).toBeDefined();
      expect(result.current.turnsByNumber[1].isStreaming).toBe(true);
    });

    it('should ignore events for different campaigns', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnStarted({
          turn_number: 1,
          session_id: 'different-campaign',
        });
      });

      expect(result.current.processingTurn).toBeNull();
      expect(result.current.turnsByNumber[1]).toBeUndefined();
    });

    it('should handle turn_message with turn_input type', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'turn_input',
          content: { combined_prompt: 'Player action' },
        });
      });

      expect(result.current.turnsByNumber[1].input).toEqual({
        combined_prompt: 'Player action',
      });
    });

    it('should handle turn_message with streaming type', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'streaming',
          content: 'Hello ',
        });
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'streaming',
          content: 'world!',
        });
      });

      expect(result.current.turnsByNumber[1].streamingText).toBe('Hello world!');
      expect(result.current.turnsByNumber[1].isStreaming).toBe(true);
    });

    it('should handle turn_message with final type', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnMessage({
          message_id: 'msg-1',
          turn_number: 1,
          response_index: 2,
          response_type: 'final',
          role: 'assistant',
          content: 'The adventure begins!',
          character_name: 'DM',
          has_audio: false,
        });
      });

      expect(result.current.turnsByNumber[1].finalMessage).toMatchObject({
        message_id: 'msg-1',
        turn_number: 1,
        content: 'The adventure begins!',
        character_name: 'DM',
      });
      expect(result.current.turnsByNumber[1].isStreaming).toBe(false);
    });

    it('should handle turn_complete event', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Start a turn
      act(() => {
        result.current.handleTurnStarted({
          turn_number: 1,
          session_id: 'campaign-123',
        });
      });

      expect(result.current.isProcessing).toBe(true);

      // Complete the turn
      act(() => {
        result.current.handleTurnComplete({
          turn_number: 1,
          session_id: 'campaign-123',
        });
      });

      expect(result.current.processingTurn).toBeNull();
      expect(result.current.turnsByNumber[1].isStreaming).toBe(false);
    });

    it('should handle turn_error event', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnStarted({
          turn_number: 1,
          session_id: 'campaign-123',
        });
      });

      act(() => {
        result.current.handleTurnError({
          turn_number: 1,
          session_id: 'campaign-123',
          error: 'Something went wrong',
        });
      });

      expect(result.current.turnsByNumber[1].error).toBe('Something went wrong');
      expect(result.current.turnsByNumber[1].isStreaming).toBe(false);
      expect(result.current.processingTurn).toBeNull();
    });

    it('should clear turns correctly', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Add some turns
      act(() => {
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
        result.current.handleTurnStarted({ turn_number: 2, session_id: 'campaign-123' });
      });

      expect(Object.keys(result.current.turnsByNumber).length).toBe(2);

      // Clear
      act(() => {
        result.current.clearTurns();
      });

      expect(result.current.turns).toEqual([]);
      expect(result.current.turnsByNumber).toEqual({});
      expect(result.current.currentTurnNumber).toBe(0);
    });
  });

  // ===========================================================================
  // History Loading Tests
  // ===========================================================================

  describe('History Loading', () => {
    it('should load turns from history messages', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      const historyMessages = [
        { turn_number: 1, response_type: 'turn_input', content: { combined_prompt: 'Action 1' } },
        { turn_number: 1, response_type: 'final', content: 'Response 1', message_id: 'msg-1' },
        { turn_number: 2, response_type: 'turn_input', content: { combined_prompt: 'Action 2' } },
        { turn_number: 2, response_type: 'final', content: 'Response 2', message_id: 'msg-2' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      expect(result.current.turns.length).toBe(2);
      expect(result.current.turnsByNumber[1].input).toEqual({ combined_prompt: 'Action 1' });
      expect(result.current.turnsByNumber[1].finalMessage.content).toBe('Response 1');
      expect(result.current.turnsByNumber[2].input).toEqual({ combined_prompt: 'Action 2' });
    });

    it('should skip messages without turn_number', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Valid' },
        { response_type: 'final', content: 'No turn number' }, // Missing turn_number
        { turn_number: null, response_type: 'final', content: 'Null turn' }, // Null turn_number
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      expect(result.current.turns.length).toBe(1);
      expect(result.current.turnsByNumber[1]).toBeDefined();
    });

    it('should handle empty history gracefully', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.loadTurnsFromHistory([]);
      });

      expect(result.current.turns).toEqual([]);
    });

    it('should use backendCurrentTurn when provided', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 5); // Backend says turn 5
      });

      expect(result.current.currentTurnNumber).toBe(5);
    });

    it('should mark current turn as streaming when isBackendProcessing is true', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Complete turn' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 2, true); // Backend processing turn 2
      });

      // Turn 2 should be created and marked as streaming
      expect(result.current.turnsByNumber[2]).toBeDefined();
      expect(result.current.turnsByNumber[2].isStreaming).toBe(true);
    });
  });

  // ===========================================================================
  // latestTurnRef Monotonicity Tests (Fix #1)
  // ===========================================================================

  describe('latestTurnRef Monotonicity', () => {
    it('should never regress latestTurnRef when WebSocket is ahead of history', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Simulate WebSocket events advancing to turn 5
      act(() => {
        result.current.handleTurnStarted({ turn_number: 5, session_id: 'campaign-123' });
      });

      expect(result.current.currentTurnNumber).toBe(5);

      // Load history that only goes up to turn 4
      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2' },
        { turn_number: 3, response_type: 'final', content: 'Turn 3' },
        { turn_number: 4, response_type: 'final', content: 'Turn 4' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 4);
      });

      // latestTurnRef should NOT regress - should stay at 5
      expect(result.current.currentTurnNumber).toBe(5);
    });

    it('should advance latestTurnRef when history has newer turns', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Start with turn 2 from WebSocket
      act(() => {
        result.current.handleTurnStarted({ turn_number: 2, session_id: 'campaign-123' });
      });

      expect(result.current.currentTurnNumber).toBe(2);

      // Load history that goes up to turn 7
      const historyMessages = [
        { turn_number: 5, response_type: 'final', content: 'Turn 5' },
        { turn_number: 6, response_type: 'final', content: 'Turn 6' },
        { turn_number: 7, response_type: 'final', content: 'Turn 7' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 7);
      });

      // latestTurnRef should advance to 7
      expect(result.current.currentTurnNumber).toBe(7);
    });

    it('should use max of currentRef, finalTurn, and merged keys', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket has turn 3
      act(() => {
        result.current.handleTurnStarted({ turn_number: 3, session_id: 'campaign-123' });
      });

      // History has turns 1, 2, 10 but backendCurrentTurn says 5
      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2' },
        { turn_number: 10, response_type: 'final', content: 'Turn 10' }, // Gap in turns
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 5);
      });

      // Should be max(3, 5, 10) = 10
      expect(result.current.currentTurnNumber).toBe(10);
    });

    it('should preserve turn ref across multiple history loads', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // First history load to turn 5
      act(() => {
        result.current.loadTurnsFromHistory(
          [{ turn_number: 5, response_type: 'final', content: 'Turn 5' }],
          5
        );
      });

      expect(result.current.currentTurnNumber).toBe(5);

      // Second history load with older data (simulating stale API response)
      act(() => {
        result.current.loadTurnsFromHistory(
          [{ turn_number: 3, response_type: 'final', content: 'Turn 3' }],
          3
        );
      });

      // Should NOT regress
      expect(result.current.currentTurnNumber).toBe(5);
    });
  });

  // ===========================================================================
  // History vs WebSocket Data Reconciliation Tests (Fix #2)
  // ===========================================================================

  describe('History vs WebSocket Data Reconciliation', () => {
    it('should prefer history finalMessage over cached WebSocket data', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket receives a final message
      act(() => {
        result.current.handleTurnMessage({
          message_id: 'ws-msg-1',
          turn_number: 1,
          response_type: 'final',
          content: 'WebSocket cached content',
        });
      });

      expect(result.current.turnsByNumber[1].finalMessage.content).toBe('WebSocket cached content');

      // History load brings corrected/authoritative final message
      const historyMessages = [
        {
          turn_number: 1,
          response_type: 'final',
          content: 'Corrected authoritative content',
          message_id: 'hist-msg-1',
        },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      // History should win - it's the authoritative persisted source
      expect(result.current.turnsByNumber[1].finalMessage.content).toBe(
        'Corrected authoritative content'
      );
    });

    it('should fall back to WebSocket data when history finalMessage is empty', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket receives a final message
      act(() => {
        result.current.handleTurnMessage({
          message_id: 'ws-msg-1',
          turn_number: 1,
          response_type: 'final',
          content: 'WebSocket content',
        });
      });

      // History load has turn_input but no final for turn 1
      const historyMessages = [
        { turn_number: 1, response_type: 'turn_input', content: { prompt: 'Input' } },
        // No final message for turn 1
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      // Should keep WebSocket final since history doesn't have one
      expect(result.current.turnsByNumber[1].finalMessage.content).toBe('WebSocket content');
    });

    it('should preserve WebSocket input when history has none', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket receives input
      act(() => {
        result.current.handleInputReceived({
          turn_number: 2,
          session_id: 'campaign-123',
          input_text: 'Recent WebSocket input',
        });
      });

      // History doesn't have turn 2 input yet
      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2 final' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      // WebSocket input should be preserved
      expect(result.current.turnsByNumber[2].input.combined_prompt).toBe('Recent WebSocket input');
    });

    it('should preserve streaming state during history merge', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket indicates turn 3 is streaming
      act(() => {
        result.current.handleTurnStarted({ turn_number: 3, session_id: 'campaign-123' });
        result.current.handleTurnMessage({
          turn_number: 3,
          response_type: 'streaming',
          content: 'Streaming...',
        });
      });

      expect(result.current.turnsByNumber[3].isStreaming).toBe(true);

      // History load for older turns
      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      // Turn 3 should still be streaming
      expect(result.current.turnsByNumber[3].isStreaming).toBe(true);
      expect(result.current.turnsByNumber[3].streamingText).toBe('Streaming...');
    });

    it('should merge history data into existing WebSocket turns correctly', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // WebSocket has partial data for turn 1
      act(() => {
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'streaming',
          content: 'Partial stream',
        });
      });

      // History brings complete data
      const historyMessages = [
        { turn_number: 1, response_type: 'turn_input', content: { prompt: 'Full input' } },
        { turn_number: 1, response_type: 'final', content: 'Complete response', message_id: 'final-1' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages);
      });

      // Should have merged data
      expect(result.current.turnsByNumber[1].input).toEqual({ prompt: 'Full input' });
      expect(result.current.turnsByNumber[1].finalMessage.content).toBe('Complete response');
      expect(result.current.turnsByNumber[1].streamingText).toBe('Partial stream');
    });
  });

  // ===========================================================================
  // Ordered Turns Tests
  // ===========================================================================

  describe('Ordered Turns', () => {
    it('should return turns in ascending order', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Add turns out of order
      act(() => {
        result.current.handleTurnStarted({ turn_number: 5, session_id: 'campaign-123' });
        result.current.handleTurnStarted({ turn_number: 2, session_id: 'campaign-123' });
        result.current.handleTurnStarted({ turn_number: 8, session_id: 'campaign-123' });
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
      });

      const turnNumbers = result.current.turns.map((t) => t.turn_number);
      expect(turnNumbers).toEqual([1, 2, 5, 8]);
    });
  });

  // ===========================================================================
  // appendStreamingText Tests
  // ===========================================================================

  describe('appendStreamingText', () => {
    it('should append text to processing turn', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
      });

      act(() => {
        result.current.appendStreamingText('Hello ');
        result.current.appendStreamingText('world!');
      });

      expect(result.current.turnsByNumber[1].streamingText).toBe('Hello world!');
    });

    it('should set isStreaming to false when isFinal is true', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      act(() => {
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
      });

      act(() => {
        result.current.appendStreamingText('Final text', true);
      });

      expect(result.current.turnsByNumber[1].isStreaming).toBe(false);
    });

    it('should use latestTurnRef when no processingTurn', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Load history to set latestTurnRef without processingTurn
      act(() => {
        result.current.loadTurnsFromHistory([
          { turn_number: 3, response_type: 'turn_input', content: { prompt: 'Test' } },
        ]);
      });

      act(() => {
        result.current.appendStreamingText('Appended text');
      });

      expect(result.current.turnsByNumber[3].streamingText).toBe('Appended text');
    });
  });

  // ===========================================================================
  // setCurrentTurn Tests
  // ===========================================================================

  describe('setCurrentTurn', () => {
    it('should set latestTurnRef and affect subsequent operations', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // setCurrentTurn sets the ref, but currentTurnNumber is read at render time
      // To verify it works, we use it in context of other operations
      act(() => {
        result.current.setCurrentTurn(10);
        // Create a turn to trigger state update so we can observe the ref
        result.current.handleTurnStarted({ turn_number: 10, session_id: 'campaign-123' });
      });

      // Now the state update causes re-render, and currentTurnNumber reflects the ref
      expect(result.current.currentTurnNumber).toBe(10);
    });

    it('should be used by appendStreamingText when no processingTurn', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Create turn 5 with some initial state
      act(() => {
        result.current.loadTurnsFromHistory([
          { turn_number: 5, response_type: 'turn_input', content: { prompt: 'Test' } },
        ]);
      });

      // Set current turn explicitly
      act(() => {
        result.current.setCurrentTurn(5);
      });

      // appendStreamingText should use the set turn
      act(() => {
        result.current.appendStreamingText('Added via setCurrentTurn');
      });

      expect(result.current.turnsByNumber[5].streamingText).toBe('Added via setCurrentTurn');
    });

    it('should not change ref for invalid values', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Set valid value first via handleTurnStarted
      act(() => {
        result.current.handleTurnStarted({ turn_number: 5, session_id: 'campaign-123' });
      });

      expect(result.current.currentTurnNumber).toBe(5);

      // Try invalid values - these should be ignored
      act(() => {
        result.current.setCurrentTurn(null);
      });
      act(() => {
        result.current.setCurrentTurn(undefined);
      });
      act(() => {
        result.current.setCurrentTurn(-1);
      });

      // Should remain at 5 (need to trigger re-render to see current value)
      // The ref is internal, but we can verify via appendStreamingText targeting turn 5
      act(() => {
        // Clear processing turn so appendStreamingText uses latestTurnRef
        result.current.handleTurnComplete({ turn_number: 5, session_id: 'campaign-123' });
        result.current.appendStreamingText('Still turn 5');
      });

      expect(result.current.turnsByNumber[5].streamingText).toContain('Still turn 5');
    });
  });

  // ===========================================================================
  // Integration Scenarios
  // ===========================================================================

  describe('Integration Scenarios', () => {
    it('should handle full turn lifecycle: start -> input -> stream -> final -> complete', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // 1. Turn starts
      act(() => {
        result.current.handleTurnStarted({ turn_number: 1, session_id: 'campaign-123' });
      });
      expect(result.current.isProcessing).toBe(true);

      // 2. Input received
      act(() => {
        result.current.handleInputReceived({
          turn_number: 1,
          session_id: 'campaign-123',
          input_text: 'I search the room',
        });
      });
      expect(result.current.turnsByNumber[1].input.combined_prompt).toBe('I search the room');

      // 3. Streaming chunks
      act(() => {
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'streaming',
          content: 'You search ',
        });
        result.current.handleTurnMessage({
          turn_number: 1,
          response_type: 'streaming',
          content: 'the dusty room...',
        });
      });
      expect(result.current.turnsByNumber[1].streamingText).toBe('You search the dusty room...');

      // 4. Final message
      act(() => {
        result.current.handleTurnMessage({
          message_id: 'msg-final',
          turn_number: 1,
          response_type: 'final',
          content: 'You find a hidden key!',
          role: 'assistant',
        });
      });
      expect(result.current.turnsByNumber[1].finalMessage.content).toBe('You find a hidden key!');
      expect(result.current.turnsByNumber[1].isStreaming).toBe(false);

      // 5. Turn complete
      act(() => {
        result.current.handleTurnComplete({ turn_number: 1, session_id: 'campaign-123' });
      });
      expect(result.current.isProcessing).toBe(false);
    });

    it('should handle page refresh scenario: WebSocket reconnect with history reload', () => {
      const { result } = renderHook(() => useTurnBasedMessages('campaign-123'));

      // Simulate: User was on turn 5, WebSocket reconnects and fires turn_started for turn 6
      act(() => {
        result.current.handleTurnStarted({ turn_number: 6, session_id: 'campaign-123' });
        result.current.handleTurnMessage({
          turn_number: 6,
          response_type: 'streaming',
          content: 'New content...',
        });
      });

      expect(result.current.currentTurnNumber).toBe(6);
      expect(result.current.turnsByNumber[6].isStreaming).toBe(true);

      // API returns history (slightly behind WebSocket)
      const historyMessages = [
        { turn_number: 1, response_type: 'final', content: 'Turn 1' },
        { turn_number: 2, response_type: 'final', content: 'Turn 2' },
        { turn_number: 3, response_type: 'final', content: 'Turn 3' },
        { turn_number: 4, response_type: 'final', content: 'Turn 4' },
        { turn_number: 5, response_type: 'final', content: 'Turn 5' },
      ];

      act(() => {
        result.current.loadTurnsFromHistory(historyMessages, 5);
      });

      // Turn ref should NOT regress (critical fix #1)
      expect(result.current.currentTurnNumber).toBe(6);

      // All history turns should be loaded
      expect(result.current.turns.length).toBe(6);

      // Turn 6 streaming state should be preserved (critical fix #2)
      expect(result.current.turnsByNumber[6].isStreaming).toBe(true);
      expect(result.current.turnsByNumber[6].streamingText).toBe('New content...');
    });
  });
});
