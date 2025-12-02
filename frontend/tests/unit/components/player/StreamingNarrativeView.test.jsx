import React from 'react';
import { describe, it, expect, beforeAll, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';

import StreamingNarrativeView from '../../../../src/components/player/StreamingNarrativeView.jsx';

describe('StreamingNarrativeView', () => {
  let originalRequestAnimationFrame;

  beforeAll(() => {
    if (!HTMLElement.prototype.scrollTo) {
      HTMLElement.prototype.scrollTo = () => {};
    }
  });

  beforeEach(() => {
    originalRequestAnimationFrame = window.requestAnimationFrame;
    window.requestAnimationFrame = (cb) => {
      if (typeof cb === 'function') {
        cb();
      }
      return 0;
    };
  });

  afterEach(() => {
    cleanup();
    if (originalRequestAnimationFrame) {
      window.requestAnimationFrame = originalRequestAnimationFrame;
    } else {
      delete window.requestAnimationFrame;
    }
  });

  it('renders messages in chronological order even if input is reversed', () => {
    const { container } = render(
      <StreamingNarrativeView
        narrative=""
        playerResponse=""
        isNarrativeStreaming={false}
        isResponseStreaming={false}
        messages={[
          {
            id: 'newest',
            sender: 'user',
            text: 'Second to act',
            timestamp: '2024-01-02T10:00:00Z',
          },
          {
            id: 'oldest',
            sender: 'dm',
            text: 'First to speak',
            timestamp: '2024-01-01T10:00:00Z',
          },
        ]}
      />
    );

    const messageNodes = Array.from(
      container.querySelectorAll('.message-entry .message-text')
    );
    const messageTexts = messageNodes.map((node) => node.textContent);

    expect(messageTexts).toEqual(['First to speak', 'Second to act']);
  });
});
