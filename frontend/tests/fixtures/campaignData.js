// Test fixtures for campaign data
export const mockCampaign = {
  id: 'test-campaign-1',
  name: 'Test Campaign',
  description: 'A test campaign for unit tests',
  characters: [
    {
      id: 'char-1',
      name: 'Test Hero',
      class: 'Fighter',
      level: 1,
      hp: 10,
      maxHp: 10
    }
  ],
  currentScene: {
    id: 'scene-1',
    name: 'Test Scene',
    description: 'A test scene'
  },
  gameState: {
    inCombat: false,
    currentTurn: null,
    initiative: []
  }
}

export const mockCharacter = {
  id: 'test-char',
  name: 'Test Character',
  class: 'Rogue',
  level: 3,
  stats: {
    strength: 12,
    dexterity: 16,
    constitution: 14,
    intelligence: 13,
    wisdom: 11,
    charisma: 15
  },
  hp: 24,
  maxHp: 24,
  armorClass: 15
}

export const mockApiResponse = {
  success: true,
  data: mockCampaign,
  message: 'Success'
}

export const mockErrorResponse = {
  success: false,
  error: 'Test error',
  message: 'Test error message'
}