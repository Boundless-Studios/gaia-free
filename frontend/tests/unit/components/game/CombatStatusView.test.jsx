import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatStatusView from '@/components/CombatStatusView'

describe('CombatStatusView Component', () => {
  const mockCombatStatus = {
    'Alice': {
      hp: '30/30',
      ap: '3/4',
      status: []
    },
    'Goblin Scout': {
      hp: '8/15',
      ap: '4/4',
      status: ['wounded']
    },
    'Bob': {
      hp: '0/25',
      ap: '0/4',
      status: ['unconscious']
    }
  }

  const mockTurnInfo = {
    active_combatant: 'Alice',
    round: 2
  }

  beforeEach(() => {
    // Clear any previous renders
  })

  describe('Rendering Conditions', () => {
    it('renders when combat_status has data', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      expect(container.querySelector('.combat-status-view')).toBeInTheDocument()
    })

    it('returns null when combat_status is empty', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={{}}
          turnInfo={mockTurnInfo}
        />
      )

      expect(container.querySelector('.combat-status-view')).not.toBeInTheDocument()
    })

    it('returns null when combat_status is null', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={null}
          turnInfo={mockTurnInfo}
        />
      )

      expect(container.querySelector('.combat-status-view')).not.toBeInTheDocument()
    })

    it('returns null when combat_status is undefined', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={undefined}
          turnInfo={mockTurnInfo}
        />
      )

      expect(container.querySelector('.combat-status-view')).not.toBeInTheDocument()
    })
  })

  describe('Header Display', () => {
    it('shows header when showHeader is true', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
          showHeader={true}
        />
      )

      expect(screen.getByText(/Combat Status/i)).toBeInTheDocument()
    })

    it('hides header when showHeader is false', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
          showHeader={false}
        />
      )

      expect(screen.queryByText('Combat Status')).not.toBeInTheDocument()
    })

    it('displays round information when turnInfo is provided', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
          showHeader={true}
        />
      )

      expect(screen.getByText(/Round 2/i)).toBeInTheDocument()
    })

    it('does not display round when turnInfo is missing', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          showHeader={true}
        />
      )

      expect(screen.queryByText(/Round/)).not.toBeInTheDocument()
    })
  })

  describe('Combatant Cards', () => {
    it('renders a card for each combatant', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      expect(cards).toHaveLength(3)
    })

    it('displays combatant names', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      expect(screen.getByText('Alice')).toBeInTheDocument()
      expect(screen.getByText('Goblin Scout')).toBeInTheDocument()
      expect(screen.getByText('Bob')).toBeInTheDocument()
    })

    it('displays HP values', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      expect(screen.getByText('30/30')).toBeInTheDocument()
      expect(screen.getByText('8/15')).toBeInTheDocument()
      expect(screen.getByText('0/25')).toBeInTheDocument()
    })

    it('displays AP values', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      expect(screen.getByText('3/4')).toBeInTheDocument()
      expect(screen.getByText('4/4')).toBeInTheDocument()
      expect(screen.getByText('0/4')).toBeInTheDocument()
    })
  })

  describe('Active Combatant Highlighting', () => {
    it('marks active combatant with active class', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const aliceCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Alice')
      )

      expect(aliceCard).toHaveClass('active')
    })

    it('shows active indicator for active combatant', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const activeIndicators = screen.getAllByText('⚡')
      expect(activeIndicators).toHaveLength(1)
    })

    it('does not mark other combatants as active', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const goblinCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Goblin Scout')
      )

      expect(goblinCard).not.toHaveClass('active')
    })
  })

  describe('Unconscious State', () => {
    it('marks unconscious combatants with unconscious class', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const bobCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Bob')
      )

      expect(bobCard).toHaveClass('unconscious')
    })

    it('shows unconscious indicator for 0 HP combatants', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const unconsciousIndicators = screen.getAllByText('💀')
      expect(unconsciousIndicators).toHaveLength(1)
    })

    it('does not mark combatants with HP > 0 as unconscious', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const aliceCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Alice')
      )

      expect(aliceCard).not.toHaveClass('unconscious')
    })
  })

  describe('HP Bar Display', () => {
    it('renders HP bars for each combatant', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const hpBars = container.querySelectorAll('.hp-bar')
      expect(hpBars).toHaveLength(3)
    })

    it('sets HP bar width based on current/max HP percentage', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const aliceCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Alice')
      )
      const aliceHpBar = aliceCard.querySelector('.hp-bar')

      // Alice has 30/30 HP = 100%
      expect(aliceHpBar.style.width).toBe('100%')
    })

    it('sets correct HP bar width for wounded combatant', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const goblinCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Goblin Scout')
      )
      const goblinHpBar = goblinCard.querySelector('.hp-bar')

      // Goblin has 8/15 HP = 53.33%
      const expectedWidth = ((8/15) * 100).toFixed(2)
      const actualWidth = parseFloat(goblinHpBar.style.width)
      expect(actualWidth).toBeCloseTo(parseFloat(expectedWidth), 1)
    })

    it('sets 0% width for unconscious combatant', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const bobCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Bob')
      )
      const bobHpBar = bobCard.querySelector('.hp-bar')

      expect(bobHpBar.style.width).toBe('0%')
    })
  })

  describe('HP Bar Colors', () => {
    it('uses green color for full health (>75%)', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const aliceCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Alice')
      )
      const aliceHpBar = aliceCard.querySelector('.hp-bar')

      expect(aliceHpBar.style.backgroundColor).toBe('rgb(76, 175, 80)') // #4caf50
    })

    it('uses orange color for wounded (25-50%)', () => {
      const combatStatus = {
        'Warrior': {
          hp: '10/30', // 33.33%
          ap: '4/4',
          status: []
        }
      }

      const { container } = render(
        <CombatStatusView
          combatStatus={combatStatus}
          turnInfo={{active_combatant: 'Warrior', round: 1}}
        />
      )

      const hpBar = container.querySelector('.hp-bar')
      expect(hpBar.style.backgroundColor).toBe('rgb(255, 152, 0)') // #ff9800
    })

    it('uses red color for critical (0-25%)', () => {
      const combatStatus = {
        'Rogue': {
          hp: '5/30', // 16.67%
          ap: '4/4',
          status: []
        }
      }

      const { container } = render(
        <CombatStatusView
          combatStatus={combatStatus}
          turnInfo={{active_combatant: 'Rogue', round: 1}}
        />
      )

      const hpBar = container.querySelector('.hp-bar')
      expect(hpBar.style.backgroundColor).toBe('rgb(244, 67, 54)') // #f44336
    })
  })

  describe('Status Effects', () => {
    it('displays status effects when present', () => {
      render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      expect(screen.getByText('wounded')).toBeInTheDocument()
      expect(screen.getByText('unconscious')).toBeInTheDocument()
    })

    it('does not show status section when no effects present', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
        />
      )

      const cards = container.querySelectorAll('.combatant-card')
      const aliceCard = Array.from(cards).find(card =>
        card.querySelector('.combatant-name')?.textContent.includes('Alice')
      )

      expect(aliceCard.querySelector('.status-effects')).not.toBeInTheDocument()
    })

    it('renders multiple status effects', () => {
      const combatStatus = {
        'Wizard': {
          hp: '20/25',
          ap: '2/4',
          status: ['poisoned', 'slowed', 'burning']
        }
      }

      render(
        <CombatStatusView
          combatStatus={combatStatus}
          turnInfo={{active_combatant: 'Wizard', round: 1}}
        />
      )

      expect(screen.getByText('poisoned')).toBeInTheDocument()
      expect(screen.getByText('slowed')).toBeInTheDocument()
      expect(screen.getByText('burning')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles Unknown HP/AP values', () => {
      const combatStatus = {
        'Mystery': {
          hp: 'Unknown',
          ap: 'Unknown',
          status: []
        }
      }

      render(
        <CombatStatusView
          combatStatus={combatStatus}
          turnInfo={{active_combatant: 'Mystery', round: 1}}
        />
      )

      expect(screen.getAllByText('Unknown')).toHaveLength(2)
    })

    it('handles N/A HP/AP values', () => {
      const combatStatus = {
        'Object': {
          hp: 'N/A',
          ap: 'N/A',
          status: []
        }
      }

      render(
        <CombatStatusView
          combatStatus={combatStatus}
          turnInfo={{active_combatant: 'Object', round: 1}}
        />
      )

      expect(screen.getAllByText('N/A')).toHaveLength(2)
    })

    it('applies custom className prop', () => {
      const { container } = render(
        <CombatStatusView
          combatStatus={mockCombatStatus}
          turnInfo={mockTurnInfo}
          className="custom-class"
        />
      )

      const view = container.querySelector('.combat-status-view')
      expect(view).toHaveClass('custom-class')
    })
  })
})
