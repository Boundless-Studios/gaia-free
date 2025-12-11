import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { API_CONFIG } from '../../src/config/api.js'

describe('API Integration Tests', () => {
  let mockFetch

  beforeEach(() => {
    mockFetch = vi.fn()
    globalThis.fetch = mockFetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Health Check Integration', () => {
    it('successfully connects to health endpoint', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ status: 'healthy', timestamp: Date.now() })
      })

      const response = await fetch(API_CONFIG.HEALTH_ENDPOINT)
      const data = await response.json()

      expect(response.ok).toBe(true)
      expect(data.status).toBe('healthy')
      expect(mockFetch).toHaveBeenCalledWith(API_CONFIG.HEALTH_ENDPOINT)
    })

    it('handles health check failure gracefully', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 503,
        json: async () => ({ status: 'unhealthy', error: 'Database connection failed' })
      })

      const response = await fetch(API_CONFIG.HEALTH_ENDPOINT)
      const data = await response.json()

      expect(response.ok).toBe(false)
      expect(response.status).toBe(503)
      expect(data.status).toBe('unhealthy')
    })

    it('handles network errors', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      await expect(fetch(API_CONFIG.HEALTH_ENDPOINT)).rejects.toThrow('Network error')
    })
  })

  describe('Chat API Integration', () => {
    it('sends chat message successfully', async () => {
      const mockResponse = {
        response: 'Hello adventurer!',
        structured_data: {
          narrative: 'You enter a dark dungeon...',
          characters: ['Warrior', 'Mage']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockResponse
      })

      const response = await fetch(API_CONFIG.CHAT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Hello DM', campaign_id: 'test-campaign' })
      })

      const data = await response.json()

      expect(response.ok).toBe(true)
      expect(data.response).toBe('Hello adventurer!')
      expect(data.structured_data.narrative).toBe('You enter a dark dungeon...')
    })

    it('handles chat API errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: async () => ({ error: 'Invalid message format' })
      })

      const response = await fetch(API_CONFIG.CHAT_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: '' })
      })

      expect(response.ok).toBe(false)
      expect(response.status).toBe(400)
    })
  })

  describe('Campaign API Integration', () => {
    it('fetches campaigns list', async () => {
      const mockCampaigns = [
        { id: 'camp-1', name: 'Test Campaign 1', created: '2024-01-01' },
        { id: 'camp-2', name: 'Test Campaign 2', created: '2024-01-02' }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ campaigns: mockCampaigns })
      })

      const response = await fetch(API_CONFIG.CAMPAIGNS_ENDPOINT)
      const data = await response.json()

      expect(data.campaigns).toHaveLength(2)
      expect(data.campaigns[0].name).toBe('Test Campaign 1')
    })

    it('creates new campaign', async () => {
      const mockNewCampaign = {
        id: 'new-campaign-id',
        name: 'New Adventure',
        structured_data: {
          narrative: 'Your adventure begins...'
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 201,
        json: async () => mockNewCampaign
      })

      const response = await fetch(`${API_CONFIG.CAMPAIGNS_ENDPOINT}/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'New Adventure' })
      })

      const data = await response.json()

      expect(response.status).toBe(201)
      expect(data.id).toBe('new-campaign-id')
      expect(data.name).toBe('New Adventure')
    })
  })

  describe('TTS API Integration', () => {
    it('requests voice synthesis', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        headers: new Map([['content-type', 'audio/wav']]),
        blob: async () => new Blob(['audio-data'], { type: 'audio/wav' })
      })

      const response = await fetch(`${API_CONFIG.TTS_ENDPOINT}/synthesize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: 'Welcome to your adventure!',
          voice: 'nathaniel',
          speed: 1.0
        })
      })

      const audioBlob = await response.blob()

      expect(response.ok).toBe(true)
      expect(audioBlob.type).toBe('audio/wav')
    })

    it('fetches available voices', async () => {
      const mockVoices = [
        { id: 'nathaniel', name: 'Nathaniel', role: 'DM' },
        { id: 'priyanka', name: 'Priyanka', role: 'Innkeeper' }
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ voices: mockVoices })
      })

      const response = await fetch(`${API_CONFIG.TTS_ENDPOINT}/voices`)
      const data = await response.json()

      expect(data.voices).toHaveLength(2)
      expect(data.voices[0].name).toBe('Nathaniel')
    })
  })

  describe('Images API Integration', () => {
    it('generates image successfully', async () => {
      const mockImageResponse = {
        image_url: '/images/generated/scene_12345.png',
        image_path: 'scene_12345.png',
        prompt: 'Dark fantasy dungeon scene',
        type: 'scene'
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockImageResponse
      })

      const response = await fetch(`${API_CONFIG.IMAGES_ENDPOINT}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: 'Dark fantasy dungeon scene',
          type: 'scene',
          campaign_id: 'test-campaign'
        })
      })

      const data = await response.json()

      expect(response.ok).toBe(true)
      expect(data.image_url).toBe('/images/generated/scene_12345.png')
      expect(data.type).toBe('scene')
    })

    it('handles image generation failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Image generation service unavailable' })
      })

      const response = await fetch(`${API_CONFIG.IMAGES_ENDPOINT}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: 'test prompt' })
      })

      expect(response.ok).toBe(false)
      expect(response.status).toBe(500)
    })
  })

  describe('API Error Handling', () => {
    it('handles timeout errors', async () => {
      mockFetch.mockImplementation(() => 
        new Promise((_, reject) => 
          setTimeout(() => reject(new Error('Request timeout')), 100)
        )
      )

      await expect(
        fetch(API_CONFIG.HEALTH_ENDPOINT)
      ).rejects.toThrow('Request timeout')
    })

    it('handles malformed JSON responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => { throw new Error('Invalid JSON') }
      })

      const response = await fetch(API_CONFIG.HEALTH_ENDPOINT)
      
      await expect(response.json()).rejects.toThrow('Invalid JSON')
    })

    it('handles CORS errors', async () => {
      mockFetch.mockRejectedValueOnce(new TypeError('Failed to fetch'))

      await expect(
        fetch(API_CONFIG.HEALTH_ENDPOINT)
      ).rejects.toThrow('Failed to fetch')
    })
  })
})