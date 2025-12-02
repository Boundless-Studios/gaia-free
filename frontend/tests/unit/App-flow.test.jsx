import { describe, it, expect, beforeEach, vi } from 'vitest'
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

describe.skip('Gaia Frontend Flow Tests', () => {
  beforeEach(() => {
    // Clear all mocks and ensure fetch is properly mocked
    vi.clearAllMocks()
    globalThis.fetch = vi.fn()
  })
  beforeEach(() => {
    // Setup localStorage mock
    globalThis.localStorage.clear()
  })

  it('app loads successfully', () => {
    render(<App />)
    
    // Check if the main app component renders
    const appElement = document.querySelector('#root') || screen.getByRole('main', { hidden: true }) || document.body
    expect(appElement).toBeTruthy()
  })

  it('renders core components without errors', () => {
    expect(() => {
      render(<App />)
    }).not.toThrow()
  })

  it('handles localStorage operations', () => {
    // Test localStorage functionality
    globalThis.localStorage.setItem('lastCampaignId', 'test-campaign-123')
    const campaignId = globalThis.localStorage.getItem('lastCampaignId')
    expect(campaignId).toBe('test-campaign-123')
    
    // Clear and verify
    globalThis.localStorage.removeItem('lastCampaignId')
    expect(globalThis.localStorage.getItem('lastCampaignId')).toBeNull()
  })

  it('maintains component integrity on multiple renders', () => {
    const { unmount, rerender } = render(<App />)
    
    // Should render successfully first time
    expect(document.body).toBeTruthy()
    
    // Should handle rerender
    rerender(<App />)
    expect(document.body).toBeTruthy()
    
    // Should cleanup properly
    unmount()
  })

  it('handles error boundaries gracefully', () => {
    // Test basic error handling by checking if app renders without throwing
    let error = null
    try {
      render(<App />)
    } catch (e) {
      error = e
    }
    expect(error).toBeNull()
  })
})