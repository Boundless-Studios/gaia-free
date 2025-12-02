import React from 'react';
import { describe, it, beforeEach, afterAll, expect, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AudioQueueProvider, useAudioQueue, AUDIO_NOTIFICATION_EVENT } from '../../../../src/context/audioQueueContext.jsx';
import { DevAuthProvider } from '../../../../src/contexts/Auth0Context.jsx';
import AudioPlayerBar from '../../../../src/components/audio/AudioPlayerBar.jsx';
import { AudioStreamProvider } from '../../../../src/context/audioStreamContext.jsx';

class MockAudio {
  static instances = [];

  constructor() {
    this.listeners = {};
    this.currentTime = 0;
    this.volume = 1;
    this.muted = false;
    this.src = '';
    this.playMock = vi.fn(() => Promise.resolve());
    this.pause = vi.fn();
    this.load = vi.fn();
    this.removeAttribute = vi.fn();
    this.setAttribute = vi.fn();
    MockAudio.instances.push(this);
  }

  play() {
    return this.playMock();
  }

  addEventListener(event, handler) {
    this.listeners[event] = handler;
  }

  removeEventListener(event) {
    delete this.listeners[event];
  }

  dispatch(eventName) {
    if (this.listeners[eventName]) {
      this.listeners[eventName]();
    }
  }
}

const enqueueTrack = (queue, overrides = {}) => {
  queue.enqueue({
    id: 'track-1',
    sessionId: 'session-1',
    url: 'https://example.com/audio.mp3',
    mimeType: 'audio/mpeg',
    durationSec: 1.5,
    createdAt: '2024-11-19T10:00:00Z',
    ...overrides,
  });
};

beforeEach(() => {
  MockAudio.instances = [];
  global.Audio = MockAudio;
  localStorage.clear();
});

afterAll(() => {
  delete global.Audio;
});

const QueueProbe = () => {
  const queue = useAudioQueue();
  return (
    <>
      <button type="button" data-testid="enqueue" onClick={() => enqueueTrack(queue)}>enqueue</button>
      <div data-testid="current-track">{queue.currentTrack?.id || 'none'}</div>
    </>
  );
};

describe('AudioQueueProvider', () => {
  it('queues audio tracks and starts playback', async () => {
    render(
      <DevAuthProvider>
        <AudioStreamProvider>
          <AudioQueueProvider>
            <QueueProbe />
          </AudioQueueProvider>
        </AudioStreamProvider>
      </DevAuthProvider>
    );

    await userEvent.click(screen.getByTestId('enqueue'));

    await waitFor(() => {
      expect(screen.getByTestId('current-track').textContent).toBe('track-1');
    });

    const instance = MockAudio.instances[0];
    expect(instance.playMock).toHaveBeenCalled();

    act(() => {
      instance.dispatch('ended');
    });

    await waitFor(() => {
      expect(screen.getByTestId('current-track').textContent).toBe('none');
    });
  });
});

describe('AudioPlayerBar', () => {
  const Harness = () => {
    const queue = useAudioQueue();
    return (
      <div>
        <button type="button" data-testid="queue-track" onClick={() => enqueueTrack(queue)}>queue</button>
        <AudioPlayerBar sessionId="session-1" />
      </div>
    );
  };

  it('renders controls and toggles mute state', async () => {
    render(
      <DevAuthProvider>
        <AudioStreamProvider>
          <AudioQueueProvider>
            <Harness />
          </AudioQueueProvider>
        </AudioStreamProvider>
      </DevAuthProvider>
    );

    const instance = MockAudio.instances[0];
    await userEvent.click(screen.getByTestId('queue-track'));

    await waitFor(() => {
      expect(screen.getByText(/Now playing/i)).toBeInTheDocument();
    });

    const muteButton = screen.getByRole('button', { name: /mute narration audio/i });
    expect(muteButton.getAttribute('aria-pressed')).toBe('false');
    await userEvent.click(muteButton);
    expect(muteButton.getAttribute('aria-pressed')).toBe('true');

    act(() => {
      instance.dispatch('ended');
    });
  });

  it('prompts to enable audio when autoplay is blocked', async () => {
    render(
      <DevAuthProvider>
        <AudioQueueProvider>
          <Harness />
        </AudioQueueProvider>
      </DevAuthProvider>
    );

    const instance = MockAudio.instances[0];
    instance.playMock.mockRejectedValueOnce({ name: 'NotAllowedError' });

    await userEvent.click(screen.getByTestId('queue-track'));

    const enableButton = await screen.findByRole('button', { name: /enable audio playback/i });
    expect(enableButton).toBeInTheDocument();

    instance.playMock.mockResolvedValue(Promise.resolve());
    await userEvent.click(enableButton);

    await waitFor(() => {
      expect(instance.playMock).toHaveBeenCalledTimes(2);
    });
  });

  it('dispatches notification events when playback repeatedly fails', async () => {
    vi.useFakeTimers();
    const listener = vi.fn();
    window.addEventListener(AUDIO_NOTIFICATION_EVENT, listener);

    render(
      <DevAuthProvider>
        <AudioQueueProvider>
          <Harness />
        </AudioQueueProvider>
      </DevAuthProvider>
    );

    const instance = MockAudio.instances[0];
    await userEvent.click(screen.getByTestId('queue-track'));

    await waitFor(() => {
      expect(instance.playMock).toHaveBeenCalledTimes(1);
    });

    act(() => {
      instance.dispatch('error');
    });

    await waitFor(() => {
      expect(listener).toHaveBeenCalled();
    });
    expect(listener.mock.calls[0][0].detail.message).toMatch(/retrying/i);

    await act(async () => {
      vi.runOnlyPendingTimers();
    });

    act(() => {
      instance.dispatch('error');
    });

    await act(async () => {
      vi.runOnlyPendingTimers();
    });

    act(() => {
      instance.dispatch('error');
    });

    await act(async () => {
      vi.runAllTimers();
    });

    await waitFor(() => {
      expect(listener.mock.calls.some((call) => call[0].detail.message.includes('removed'))).toBe(true);
    });

    window.removeEventListener(AUDIO_NOTIFICATION_EVENT, listener);
    vi.useRealTimers();
  });
});
