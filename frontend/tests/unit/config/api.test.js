import { describe, it, expect, beforeEach, vi } from 'vitest'
import { API_CONFIG } from '../../../src/config/api.js'

describe('API Configuration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uses default localhost URLs when no environment override', () => {
    expect(API_CONFIG.BACKEND_URL).toBe('http://test-mock-server:8000')
  })

  it('generates correct endpoint URLs', () => {
    expect(API_CONFIG.HEALTH_ENDPOINT).toBe('http://test-mock-server:8000/api/health')
    expect(API_CONFIG.TTS_ENDPOINT).toBe('http://test-mock-server:8000/api/tts')
    expect(API_CONFIG.IMAGES_ENDPOINT).toBe('http://test-mock-server:8000/api/images')
    expect(API_CONFIG.CAMPAIGNS_ENDPOINT).toBe('http://test-mock-server:8000/api/campaigns')
    expect(API_CONFIG.TEST_ENDPOINT).toBe('http://test-mock-server:8000/api/test')
  })

  it('exports configuration object', () => {
    expect(API_CONFIG).toBeDefined()
    expect(typeof API_CONFIG).toBe('object')
    expect(API_CONFIG.BACKEND_URL).toBeDefined()
  })

  it('has all required endpoints', () => {
    expect(API_CONFIG.HEALTH_ENDPOINT).toContain('/api/health')
    expect(API_CONFIG.TTS_ENDPOINT).toContain('/api/tts')
    expect(API_CONFIG.IMAGES_ENDPOINT).toContain('/api/images')
    expect(API_CONFIG.CAMPAIGNS_ENDPOINT).toContain('/api/campaigns')
  })

  it('backend URL is a valid URL', () => {
    expect(API_CONFIG.BACKEND_URL).toMatch(/^https?:\/\//)
  })
})