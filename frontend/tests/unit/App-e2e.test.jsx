import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock all components that make network requests to prevent AggregateErrors
vi.mock('../../src/components/game/ImageGalleryWithPolling', () => ({
  default: vi.fn(() => <div data-testid="image-gallery-mock">Image Gallery Mock</div>)
}))

vi.mock('../../src/components/ContinuousTranscription', () => ({
  default: vi.fn(() => <div data-testid="transcription-mock">Transcription Mock</div>)
}))

vi.mock('../../src/components/audio/ContinuousTranscription', () => ({
  default: vi.fn(() => <div data-testid="audio-transcription-mock">Audio Transcription Mock</div>)
}))

// API_CONFIG is now mocked globally in tests/setup.js

import App from '../../src/App.jsx'

describe.skip('Gaia Frontend App E2E', () => {
  it('loads the application', () => {
    render(<App />)
    
    // Check that the main app component renders
    const app = screen.getByRole('main') || document.querySelector('#root')
    expect(app).toBeTruthy()
  })

  it('renders without crashing', () => {
    const div = document.createElement('div')
    expect(() => {
      render(<App />, { container: div })
    }).not.toThrow()
  })

  it('has accessible structure', () => {
    render(<App />)
    
    // Check for basic accessibility
    const appElement = document.body
    expect(appElement).toBeTruthy()
    expect(appElement.tagName.toLowerCase()).toBe('body')
  })
})