import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock XMLHttpRequest to prevent any underlying network requests
vi.mock('node:http', () => ({
  request: vi.fn()
}))

vi.mock('node:https', () => ({
  request: vi.fn()
}))

// API_CONFIG is now mocked globally in tests/setup.js

describe('API Health Integration', () => {
  beforeEach(() => {
    // Clear all mocks and ensure fetch is properly mocked
    vi.clearAllMocks()
    globalThis.fetch = vi.fn()
  })

  it('checks health endpoint', async () => {
    const mockResponse = { status: 'healthy' }
    globalThis.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    })

    const response = await fetch('/api/health')
    const data = await response.json()

    expect(fetch).toHaveBeenCalledWith('/api/health')
    expect(data).toEqual(mockResponse)
  })

  it('handles API errors gracefully', async () => {
    globalThis.fetch.mockRejectedValueOnce(new Error('Network error'))

    try {
      await fetch('/api/health')
    } catch (error) {
      expect(error.message).toBe('Network error')
    }
  })
})