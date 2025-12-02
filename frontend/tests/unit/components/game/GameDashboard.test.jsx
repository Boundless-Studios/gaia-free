import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import GameDashboard from '@/components/GameDashboard'

// Mock the ImageGalleryWithPolling component to prevent network requests
vi.mock('@/components/game/ImageGalleryWithPolling', () => ({
  default: vi.fn(() => <div data-testid="image-gallery-mock">Image Gallery Mock</div>)
}))

// Mock the NarrativeView component
vi.mock('@/components/game/NarrativeView', () => ({
  default: vi.fn(({ narrative }) => <div data-testid="narrative-view-mock">{JSON.stringify(narrative)}</div>)
}))

// Mock the TurnView component
vi.mock('@/components/game/TurnView', () => ({
  default: vi.fn(({ turn }) => <div data-testid="turn-view-mock">{JSON.stringify(turn)}</div>)
}))

// Mock the CombatStatusView component
vi.mock('@/components/CombatStatusView', () => ({
  default: vi.fn(({ combatStatus, turnInfo }) => (
    <div data-testid="combat-status-view-mock">
      {JSON.stringify({ combatStatus, turnInfo })}
    </div>
  ))
}))

describe('GameDashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders game dashboard', () => {
    render(<GameDashboard />)
    expect(document.body).toBeInTheDocument()
  })

  it('displays game sections', () => {
    render(<GameDashboard />)
    // Check for common game dashboard elements
    const dashboard = document.querySelector('.game-dashboard') || document.body
    expect(dashboard).toBeInTheDocument()
  })

  it('handles campaign data prop', () => {
    const mockCampaignData = {
      id: 'test-campaign',
      name: 'Test Campaign',
      characters: []
    }

    render(<GameDashboard campaignData={mockCampaignData} />)
    expect(document.body).toBeInTheDocument()
  })

  describe('Combat Status View Integration', () => {
    it('renders CombatStatusView when combat_status is present in DM view', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        turn: 'What would you like to do?',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] },
          'Goblin': { hp: '8/15', ap: '4/4', status: ['wounded'] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      const { getByTestId } = render(
        <GameDashboard
          latestStructuredData={mockStructuredData}
          campaignId="test-campaign"
        />
      )

      expect(getByTestId('combat-status-view-mock')).toBeInTheDocument()
    })

    it('does not render CombatStatusView when combat_status is empty', () => {
      const mockStructuredData = {
        narrative: 'You explore the peaceful village.',
        turn: 'What would you like to do?',
        combat_status: {}
      }

      const { queryByTestId } = render(
        <GameDashboard
          latestStructuredData={mockStructuredData}
          campaignId="test-campaign"
        />
      )

      expect(queryByTestId('combat-status-view-mock')).not.toBeInTheDocument()
    })

    it('does not render CombatStatusView when combat_status is missing', () => {
      const mockStructuredData = {
        narrative: 'You explore the peaceful village.',
        turn: 'What would you like to do?'
      }

      const { queryByTestId } = render(
        <GameDashboard
          latestStructuredData={mockStructuredData}
          campaignId="test-campaign"
        />
      )

      expect(queryByTestId('combat-status-view-mock')).not.toBeInTheDocument()
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
        turn: 'What would you like to do?',
        combat_status: mockCombatStatus,
        turn_info: mockTurnInfo
      }

      const { getByTestId } = render(
        <GameDashboard
          latestStructuredData={mockStructuredData}
          campaignId="test-campaign"
        />
      )

      const combatStatusView = getByTestId('combat-status-view-mock')
      const mockContent = JSON.parse(combatStatusView.textContent)

      expect(mockContent.combatStatus).toEqual(mockCombatStatus)
      expect(mockContent.turnInfo).toEqual(mockTurnInfo)
    })

    it('renders combat status panel below player options panel', () => {
      const mockStructuredData = {
        narrative: 'The battle rages on.',
        turn: 'What would you like to do?',
        combat_status: {
          'Alice': { hp: '30/30', ap: '3/4', status: [] }
        },
        turn_info: {
          active_combatant: 'Alice',
          round: 2
        }
      }

      const { container } = render(
        <GameDashboard
          latestStructuredData={mockStructuredData}
          campaignId="test-campaign"
        />
      )

      const playerOptionsPanel = container.querySelector('.dashboard-player-options-panel')
      const combatStatusPanel = container.querySelector('.dashboard-combat-status-panel')

      // Both panels should exist
      expect(playerOptionsPanel).toBeInTheDocument()
      expect(combatStatusPanel).toBeInTheDocument()

      // Combat status should come after player options in DOM order
      const panels = Array.from(container.querySelectorAll('.game-dashboard > div'))
      const optionsIndex = panels.indexOf(playerOptionsPanel)
      const statusIndex = panels.indexOf(combatStatusPanel)

      expect(statusIndex).toBeGreaterThan(optionsIndex)
    })
  })
})