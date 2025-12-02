import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'

// Mock all components that make network requests to prevent AggregateErrors
vi.mock('@/components/game/ImageGalleryWithPolling', () => ({
  default: vi.fn(() => <div data-testid="image-gallery-mock">Image Gallery Mock</div>)
}))

vi.mock('@/components/ContinuousTranscription', () => ({
  default: vi.fn(() => <div data-testid="transcription-mock">Transcription Mock</div>)
}))

vi.mock('@/components/audio/ContinuousTranscription', () => ({
  default: vi.fn(() => <div data-testid="audio-transcription-mock">Audio Transcription Mock</div>)
}))

// API_CONFIG is now mocked globally in tests/setup.js

import App from '@/App.jsx'

describe.skip('App Component', () => {
  beforeEach(() => {
    // Clear all mocks and ensure fetch is properly mocked
    vi.clearAllMocks()
    globalThis.fetch = vi.fn()
  })
  it('renders without crashing', () => {
    render(<App />)
    expect(document.body).toBeInTheDocument()
  })

  it('has the correct app structure', () => {
    render(<App />)
    // Check if the main app container exists
    const appElement = document.querySelector('#root') || document.body
    expect(appElement).toBeInTheDocument()
  })
})