import React, { useState, useCallback, useRef } from 'react';
import StreamingNarrativeView from '../components/player/StreamingNarrativeView.jsx';

/**
 * Test page for StreamingNarrativeView component
 * Simulates the message flow to debug duplicate message issues
 *
 * Access at: /test/streaming-narrative
 */
const StreamingNarrativeTest = () => {
  // Message history state
  const [messages, setMessages] = useState([]);

  // Streaming state
  const [streamingNarrative, setStreamingNarrative] = useState('');
  const [streamingResponse, setStreamingResponse] = useState('');
  const [isNarrativeStreaming, setIsNarrativeStreaming] = useState(false);
  const [isResponseStreaming, setIsResponseStreaming] = useState(false);

  // Test controls
  const [testLog, setTestLog] = useState([]);
  const messageIdCounter = useRef(0);

  const log = useCallback((message) => {
    const timestamp = new Date().toISOString();
    console.log(`[TEST] ${timestamp}: ${message}`);
    setTestLog(prev => [...prev.slice(-20), `${timestamp.split('T')[1].slice(0, 8)}: ${message}`]);
  }, []);

  // Simulate adding a user message
  const addUserMessage = useCallback((text) => {
    const msg = {
      id: `user-${++messageIdCounter.current}`,
      text,
      sender: 'user',
      timestamp: new Date().toISOString(),
    };
    log(`Adding user message: "${text.slice(0, 50)}..."`);
    setMessages(prev => [...prev, msg]);
    return msg;
  }, [log]);

  // Simulate adding a DM message (what happens after streaming completes)
  const addDMMessage = useCallback((text, options = {}) => {
    const timestamp = options.timestamp || new Date().toISOString();

    // Check for duplicates (same logic as useCampaignMessages)
    const normalizedText = text.replace(/\s+/g, ' ').trim();

    setMessages(prev => {
      const hasDuplicate = prev.some(msg => {
        if (msg.sender !== 'dm') return false;
        const candidateText = (msg.text || '').replace(/\s+/g, ' ').trim();
        if (candidateText !== normalizedText) return false;
        // 30 second window
        if (!msg.timestamp) return true;
        const timeDiff = Math.abs(new Date(msg.timestamp).getTime() - new Date(timestamp).getTime());
        return timeDiff <= 30000;
      });

      if (hasDuplicate) {
        log(`⚠️ DUPLICATE DETECTED - skipping message: "${text.slice(0, 50)}..."`);
        return prev;
      }

      const msg = {
        id: `dm-${++messageIdCounter.current}`,
        message_id: options.message_id || `msg_${Date.now()}`,
        text,
        sender: 'dm',
        timestamp,
        ...options,
      };
      log(`✅ Adding DM message: "${text.slice(0, 50)}..."`);
      return [...prev, msg];
    });
  }, [log]);

  // Simulate streaming a response character by character
  const simulateStreaming = useCallback(async (text, delayMs = 20) => {
    log('Starting streaming...');
    setIsNarrativeStreaming(true);
    setStreamingNarrative('');

    for (let i = 0; i < text.length; i++) {
      await new Promise(resolve => setTimeout(resolve, delayMs));
      setStreamingNarrative(text.slice(0, i + 1));
    }

    setIsNarrativeStreaming(false);
    log('Streaming complete');
    return text;
  }, [log]);

  // Simulate the full flow: user message -> streaming -> history add
  const runFullFlowTest = useCallback(async () => {
    log('=== STARTING FULL FLOW TEST ===');

    const userText = 'I attack the goblin with my sword!';
    const dmResponse = 'The goblin dodges your attack, but you manage to graze its arm. It shrieks in pain and lunges at you with renewed fury. Roll for initiative!';

    // Step 1: Add user message
    addUserMessage(userText);

    // Step 2: Simulate streaming
    await simulateStreaming(dmResponse, 10);

    // Step 3: Add to history (simulating handleCampaignUpdate)
    log('Adding streamed content to history...');
    addDMMessage(dmResponse, { isStreamed: true });

    // Step 4: Clear streaming
    log('Clearing streaming state...');
    setStreamingNarrative('');

    log('=== FULL FLOW TEST COMPLETE ===');
    log(`Messages in history: ${messages.length + 2}`); // +2 for the ones we just added
  }, [addUserMessage, addDMMessage, simulateStreaming, log, messages.length]);

  // Simulate the duplicate bug scenario
  const runDuplicateBugTest = useCallback(async () => {
    log('=== STARTING DUPLICATE BUG TEST ===');

    const userText = 'What do I see in the tavern?';
    const dmResponse = 'The tavern is dimly lit by flickering candles. You see a bartender polishing glasses, a hooded figure in the corner, and a group of adventurers playing cards.';

    // Step 1: Add user message
    addUserMessage(userText);

    // Step 2: Simulate streaming
    await simulateStreaming(dmResponse, 5);

    // Step 3: First add (simulating handleCampaignUpdate)
    log('First addDMMessage call (handleCampaignUpdate)...');
    addDMMessage(dmResponse, {
      isStreamed: true,
      timestamp: new Date().toISOString(),
    });

    // Clear streaming
    setStreamingNarrative('');

    // Step 4: Simulate a SECOND add with different timestamp (the bug!)
    // This simulates what happens when reloadHistoryAfterStream fetches from backend
    log('Second addDMMessage call (simulating backend fetch with different timestamp)...');
    await new Promise(resolve => setTimeout(resolve, 100));

    // Backend returns same text but with server timestamp (could be hours different)
    const serverTimestamp = new Date(Date.now() + 3600000).toISOString(); // 1 hour later
    addDMMessage(dmResponse, {
      isStreamed: true,
      timestamp: serverTimestamp,
      message_id: 'server_msg_123',
    });

    log('=== DUPLICATE BUG TEST COMPLETE ===');
  }, [addUserMessage, addDMMessage, simulateStreaming, log]);

  // Clear all state
  const clearAll = useCallback(() => {
    setMessages([]);
    setStreamingNarrative('');
    setStreamingResponse('');
    setIsNarrativeStreaming(false);
    setIsResponseStreaming(false);
    setTestLog([]);
    messageIdCounter.current = 0;
    log('Cleared all state');
  }, [log]);

  // Count messages by sender
  const messageCounts = messages.reduce((acc, msg) => {
    acc[msg.sender] = (acc[msg.sender] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: '#1a1a2e',
      color: '#eee',
      fontFamily: 'monospace',
    }}>
      {/* Left: StreamingNarrativeView */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        borderRight: '2px solid #333',
      }}>
        <div style={{
          padding: '10px',
          background: '#252540',
          borderBottom: '1px solid #333',
        }}>
          <h2 style={{ margin: 0 }}>StreamingNarrativeView Test</h2>
          <div style={{ fontSize: '12px', color: '#888', marginTop: '5px' }}>
            Messages: {messages.length} (User: {messageCounts.user || 0}, DM: {messageCounts.dm || 0})
            {isNarrativeStreaming && ' | 🔵 Streaming...'}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'hidden' }}>
          <StreamingNarrativeView
            narrative={streamingNarrative}
            playerResponse={streamingResponse}
            isNarrativeStreaming={isNarrativeStreaming}
            isResponseStreaming={isResponseStreaming}
            messages={messages}
            onImageGenerated={() => {}}
            campaignId="test-campaign"
          />
        </div>
      </div>

      {/* Right: Controls and Log */}
      <div style={{
        width: '400px',
        display: 'flex',
        flexDirection: 'column',
        background: '#16162a',
      }}>
        {/* Controls */}
        <div style={{
          padding: '15px',
          borderBottom: '1px solid #333',
        }}>
          <h3 style={{ margin: '0 0 15px 0' }}>Test Controls</h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <button
              onClick={runFullFlowTest}
              data-testid="run-full-flow"
              style={{
                padding: '10px',
                background: '#2ecc71',
                color: '#fff',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: 'bold',
              }}
            >
              ▶️ Run Full Flow Test
            </button>

            <button
              onClick={runDuplicateBugTest}
              data-testid="run-duplicate-test"
              style={{
                padding: '10px',
                background: '#e74c3c',
                color: '#fff',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
                fontWeight: 'bold',
              }}
            >
              🐛 Run Duplicate Bug Test
            </button>

            <button
              onClick={clearAll}
              data-testid="clear-all"
              style={{
                padding: '10px',
                background: '#555',
                color: '#fff',
                border: 'none',
                borderRadius: '5px',
                cursor: 'pointer',
              }}
            >
              🗑️ Clear All
            </button>
          </div>
        </div>

        {/* Message Count Display */}
        <div style={{
          padding: '15px',
          borderBottom: '1px solid #333',
          background: messageCounts.dm > 1 ? '#4a1c1c' : '#1c4a1c',
        }}>
          <div data-testid="dm-count" style={{ fontSize: '24px', fontWeight: 'bold' }}>
            DM Messages: {messageCounts.dm || 0}
          </div>
          {(messageCounts.dm || 0) > 1 && (
            <div style={{ color: '#ff6b6b', marginTop: '5px' }}>
              ⚠️ DUPLICATE DETECTED!
            </div>
          )}
        </div>

        {/* Log */}
        <div style={{
          flex: 1,
          overflow: 'auto',
          padding: '10px',
          fontSize: '11px',
        }}>
          <h4 style={{ margin: '0 0 10px 0' }}>Test Log</h4>
          {testLog.map((entry, i) => (
            <div
              key={i}
              style={{
                padding: '3px 0',
                borderBottom: '1px solid #333',
                color: entry.includes('DUPLICATE') ? '#ff6b6b' :
                       entry.includes('✅') ? '#2ecc71' : '#aaa',
              }}
            >
              {entry}
            </div>
          ))}
        </div>

        {/* Raw Messages Debug */}
        <div style={{
          maxHeight: '200px',
          overflow: 'auto',
          padding: '10px',
          background: '#0d0d1a',
          fontSize: '10px',
        }}>
          <h4 style={{ margin: '0 0 10px 0' }}>Raw Messages</h4>
          <pre data-testid="raw-messages" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(messages, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

export default StreamingNarrativeTest;
