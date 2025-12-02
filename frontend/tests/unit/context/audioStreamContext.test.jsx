import React from 'react';
import { describe, it, beforeEach, afterEach, expect, vi } from 'vitest';
import { render, waitFor, act } from '@testing-library/react';

import { AudioStreamProvider, useAudioStream } from '../../../src/context/audioStreamContext.jsx';
import { DevAuthProvider } from '../../../src/contexts/Auth0Context.jsx';

class MockAudio {
  static instances = [];

  constructor() {
    this.listeners = {};
    this.currentTime = 0;
    this.src = '';
    this.muted = false;
    this.volume = 1;
    this.paused = true;
    this.playMock = vi.fn(() => Promise.resolve());
    this.pause = vi.fn(() => {
      this.paused = true;
    });
    this.load = vi.fn();
    this.removeAttribute = vi.fn();
    this.setAttribute = vi.fn();
    this.addEventListener = vi.fn((event, handler) => {
      this.listeners[event] = handler;
    });
    this.removeEventListener = vi.fn((event) => {
      delete this.listeners[event];
    });
    MockAudio.instances.push(this);
  }

  play() {
    this.paused = false;
    return this.playMock();
  }
}

describe('AudioStreamProvider', () => {
  beforeEach(() => {
    MockAudio.instances = [];
    global.Audio = MockAudio;
    localStorage.clear();
  });

  afterEach(() => {
    delete global.Audio;
  });

  it('retries playback with a mute fallback when autoplay is blocked', async () => {
    const streamRef = React.createRef();

    const Consumer = React.forwardRef((_, ref) => {
      const stream = useAudioStream();
      React.useImperativeHandle(ref, () => stream, [stream]);
      return null;
    });

    render(
      <DevAuthProvider>
        <AudioStreamProvider>
          <Consumer ref={streamRef} />
        </AudioStreamProvider>
      </DevAuthProvider>
    );

    await waitFor(() => expect(streamRef.current).toBeTruthy());

    const audioInstance = MockAudio.instances[0];
    audioInstance.playMock
      .mockRejectedValueOnce({ name: 'NotAllowedError', message: 'blocked' })
      .mockResolvedValueOnce();

    await act(async () => {
      await streamRef.current.startStream(
        'session-1',
        0,
        false,
        [],
        'https://example.com/audio'
      );
    });

    expect(audioInstance.playMock).toHaveBeenCalledTimes(2);
    expect(audioInstance.muted).toBe(false);
    expect(streamRef.current.needsUserGesture).toBe(false);
  });
});
