import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PlayerView from '@/components/player/PlayerView'
import { AudioQueueProvider } from '@/context/audioQueueContext'
import { DevAuthProvider } from '@/contexts/Auth0Context'

// Mock child components - must match the relative import paths in PlayerView.jsx
vi.mock('../../../../src/components/player/CharacterSheet/CharacterSheet.jsx', () => ({
  default: vi.fn(({ character }) => (
    <div data-testid="character-sheet-mock">
      Character: {character?.name || 'Unknown'}
    </div>
  ))
}))

vi.mock('../../../../src/components/player/PlayerNarrativeView/PlayerNarrativeView.jsx', () => ({
  default: vi.fn(({ structuredData }) => (
    <div data-testid="player-narrative-mock">
      {structuredData?.narrative || 'No narrative'}
    </div>
  ))
}))

vi.mock('../../../../src/components/player/PlayerControls/PlayerControls.jsx', () => ({
  default: vi.fn(() => (
    <div data-testid="player-controls-mock">Player Controls</div>
  ))
}))

vi.mock('@/components/CombatStatusView', () => ({
  default: vi.fn(({ combatStatus, turnInfo }) => (
    <div data-testid="combat-status-view-mock">
      {JSON.stringify({ combatStatus, turnInfo })}
    </div>
  ))
}))

// Mock Audio API
class MockAudio {
  constructor() {
    this.src = ''
    this.volume = 1
    this.muted = false
    this.play = vi.fn(() => Promise.resolve())
    this.pause = vi.fn()
    this.load = vi.fn()
    this.removeAttribute = vi.fn()
    this.setAttribute = vi.fn()
    this.addEventListener = vi.fn()
    this.removeEventListener = vi.fn()
  }
}
global.Audio = MockAudio

describe('PlayerView Component', () => {
  const mockCharacter = {
    id: 'char-1',
    name: 'Alice the Brave',
    class: 'Paladin',
    level: 5,
    hp: 45,
    max_hp: 45
  }

  const mockCampaignId = 'test-campaign'
  const mockPlayerId = 'player-1'

  const renderWithProvider = (component) => {
    return render(
      <DevAuthProvider>
        <AudioQueueProvider>
          {component}
        </AudioQueueProvider>
      </DevAuthProvider>
    )
  }

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  describe('Basic Rendering', () => {
    it('renders player view with character data', () => {
      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={{}}
        />
      )

      expect(screen.getByTestId('player-view')).toBeInTheDocument()
      expect(screen.getByTestId('character-sheet-mock')).toBeInTheDocument()
    })

    it('shows character creation message when no character data', () => {
      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={null}
          latestStructuredData={{}}
        />
      )

      expect(screen.getByText('Create Your Character')).toBeInTheDocument()
    })
  })

  describe('Combat Status Toggle - Player View', () => {
    it('shows toggle buttons when combat_status is present', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] },
          'Goblin': { hp: '8/15', ap: '4/4', status: ['wounded'] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      expect(screen.getByText('👤 Character')).toBeInTheDocument()
      expect(screen.getByText('⚔️ Combat')).toBeInTheDocument()
    })

    it('does not show toggle buttons when combat_status is empty', () => {
      const mockStructuredData = {
        narrative: 'You explore the peaceful village.',
        combat_status: {}
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      expect(screen.queryByText('👤 Character')).not.toBeInTheDocument()
      expect(screen.queryByText('⚔️ Combat')).not.toBeInTheDocument()
    })

    it('does not show toggle buttons when combat_status is missing', () => {
      const mockStructuredData = {
        narrative: 'You explore the peaceful village.'
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      expect(screen.queryByText('👤 Character')).not.toBeInTheDocument()
      expect(screen.queryByText('⚔️ Combat')).not.toBeInTheDocument()
    })

    it('defaults to showing combat status when combat data is available', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        }
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      // Combat status should be visible by default when available
      expect(screen.getByTestId('combat-status-view-mock')).toBeInTheDocument()
      // Character sheet should not be visible
      expect(screen.queryByTestId('character-sheet-mock')).not.toBeInTheDocument()
    })

    it('switches to combat view when Combat button is clicked', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      // Click Combat button
      const combatButton = screen.getByText('⚔️ Combat')
      fireEvent.click(combatButton)

      // Combat status should now be visible
      expect(screen.getByTestId('combat-status-view-mock')).toBeInTheDocument()
      // Character sheet should not be visible
      expect(screen.queryByTestId('character-sheet-mock')).not.toBeInTheDocument()
    })

    it('switches back to character view when Character button is clicked', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      // First switch to combat view
      const combatButton = screen.getByText('⚔️ Combat')
      fireEvent.click(combatButton)

      // Then switch back to character view
      const characterButton = screen.getByText('👤 Character')
      fireEvent.click(characterButton)

      // Character sheet should be visible again
      expect(screen.getByTestId('character-sheet-mock')).toBeInTheDocument()
      // Combat status should not be visible
      expect(screen.queryByTestId('combat-status-view-mock')).not.toBeInTheDocument()
    })

    it('passes combat_status and turn_info to CombatStatusView', () => {
      const mockCombatStatus = {
        'Alice': { hp: '30/30', ap: '3/4', status: [] },
        'Goblin': { hp: '8/15', ap: '4/4', status: ['wounded'] }
      }
      const mockTurnInfo = {
        active_combatant: 'Alice',
        round: 2
      }
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        combat_status: mockCombatStatus,
        turn_info: mockTurnInfo
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      // Switch to combat view
      const combatButton = screen.getByText('⚔️ Combat')
      fireEvent.click(combatButton)

      const combatStatusView = screen.getByTestId('combat-status-view-mock')
      const mockContent = JSON.parse(combatStatusView.textContent)

      expect(mockContent.combatStatus).toEqual(mockCombatStatus)
      expect(mockContent.turnInfo).toEqual(mockTurnInfo)
    })

    it('passes showHeader=false to CombatStatusView', async () => {
      const mockStructuredData = {
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      const CombatStatusView = vi.mocked(
        await import('@/components/CombatStatusView')
      ).default

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      // Switch to combat view
      const combatButton = screen.getByText('⚔️ Combat')
      fireEvent.click(combatButton)

      // Check that CombatStatusView was called with showHeader=false
      expect(CombatStatusView).toHaveBeenCalledWith(
        expect.objectContaining({
          showHeader: false
        }),
        expect.anything()
      )
    })

    it('highlights active toggle button', () => {
      const mockStructuredData = {
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        }
      }

      renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={mockStructuredData}
        />
      )

      const characterButton = screen.getByText('👤 Character')
      const combatButton = screen.getByText('⚔️ Combat')

      // Combat button should be active by default when combat data is available
      expect(combatButton).toHaveClass('active')
      expect(characterButton).not.toHaveClass('active')

      // Click Character button
      fireEvent.click(characterButton)

      // Character button should now be active
      expect(characterButton).toHaveClass('active')
      expect(combatButton).not.toHaveClass('active')
    })
  })

  describe('Game State Updates', () => {
    it('updates combat status when new structured data arrives', () => {
      const initialStructuredData = {
        narrative: 'The battle begins.',
        combat_status: {
          'Alice': { hp: '30/30', ap: '4/4', status: [] }
        }
      }

      const { rerender } = renderWithProvider(
        <PlayerView
          campaignId={mockCampaignId}
          playerId={mockPlayerId}
          characterData={mockCharacter}
          latestStructuredData={initialStructuredData}
        />
      )

      // Switch to combat view
      fireEvent.click(screen.getByText('⚔️ Combat'))

      // Update with new structured data
      const updatedStructuredData = {
        narrative: 'Alice strikes!',
        combat_status: {
          'Alice': { hp: '30/30', ap: '2/4', status: [] },
          'Goblin': { hp: '5/15', ap: '4/4', status: ['wounded'] }
        },
        turn_info: {
          active_combatant: 'Goblin',
          round: 1
        }
      }

      rerender(
        <AudioQueueProvider>
          <PlayerView
            campaignId={mockCampaignId}
            playerId={mockPlayerId}
            characterData={mockCharacter}
            latestStructuredData={updatedStructuredData}
          />
        </AudioQueueProvider>
      )

      const combatStatusView = screen.getByTestId('combat-status-view-mock')
      const mockContent = JSON.parse(combatStatusView.textContent)

      expect(mockContent.combatStatus).toEqual(updatedStructuredData.combat_status)
      expect(mockContent.turnInfo).toEqual(updatedStructuredData.turn_info)
    })
  })
})
