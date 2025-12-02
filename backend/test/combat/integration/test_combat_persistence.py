"""Integration tests for combat state persistence across session restarts.

These tests validate that:
1. Combat sessions are saved to disk correctly
2. Combat sessions can be loaded from disk after restart
3. CombatStateManager properly persists combat state
4. Recovery works after simulated crash
5. Completed combats are archived properly
6. Multiple campaigns can have active combats simultaneously
"""

import pytest
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from unittest.mock import Mock

from gaia.mechanics.combat.combat_state_manager import CombatStateManager
from gaia.mechanics.combat.combat_persistence import CombatPersistenceManager
from gaia.models.combat import (
    CombatSession, CombatantState, CombatStatus,
    CombatStats, Position
)
from gaia_private.models.combat.agent_io.initiation import BattlefieldConfig
from gaia.models.character.character_info import CharacterInfo


@pytest.mark.integration
class TestCombatPersistence:
    """Test combat persistence functionality.

    These tests validate that combat state persists correctly across
    saves, loads, and system restarts.
    """

    @pytest.fixture
    def test_dir(self, tmp_path):
        """Create a temporary directory for testing."""
        test_dir = tmp_path / "test_combat_persistence"
        test_dir.mkdir(exist_ok=True)
        yield test_dir
        # Cleanup after test
        if test_dir.exists():
            shutil.rmtree(test_dir)

    @pytest.fixture
    def mock_campaign_manager(self, test_dir):
        """Create mock campaign manager for testing."""
        manager = Mock()
        manager.campaign_storage_path = test_dir

        def get_campaign_path(campaign_id: str) -> Path:
            return test_dir / campaign_id

        def get_campaign_data_path(campaign_id: str) -> Path:
            return get_campaign_path(campaign_id)

        def ensure_campaign_structure(campaign_id: str):
            campaign_path = get_campaign_path(campaign_id)
            combat_path = campaign_path / "combat"
            (combat_path / "active").mkdir(parents=True, exist_ok=True)
            (combat_path / "history").mkdir(parents=True, exist_ok=True)
            return combat_path

        def list_campaigns() -> Dict[str, Any]:
            if not test_dir.exists():
                return {"campaigns": []}

            campaigns = []
            for d in test_dir.iterdir():
                if d.is_dir():
                    campaigns.append({"id": d.name, "name": d.name})

            return {"campaigns": campaigns}

        manager.get_campaign_path = get_campaign_path
        manager.get_campaign_data_path = get_campaign_data_path
        manager.ensure_campaign_structure = ensure_campaign_structure
        manager.list_campaigns = list_campaigns

        return manager

    @pytest.fixture
    def combat_session(self):
        """Create a test combat session with sample data."""
        session = CombatSession(
            session_id="tavern_brawl - round 1",
            scene_id="tavern_brawl",
            status=CombatStatus.IN_PROGRESS,
            round_number=2,
            current_turn_index=1
        )

        # Add timestamps for archival
        session.created_at = datetime.now()
        session.updated_at = datetime.now()

        # Add player combatant
        player = CombatantState(
            character_id="player_001",
            name="Thorin",
            is_npc=False,
            initiative=15,
            hp=45,
            max_hp=50,
            ac=18,
            level=5
        )
        session.combatants[player.character_id] = player

        # Add enemy combatant
        enemy = CombatantState(
            character_id="enemy_001",
            name="Bandit Leader",
            is_npc=True,
            initiative=12,
            hp=30,
            max_hp=65,
            ac=15,
            level=3
        )
        session.combatants[enemy.character_id] = enemy

        # Set turn order (not initiative_order)
        session.turn_order = ["player_001", "enemy_001"]

        # Add battlefield config
        session.battlefield = BattlefieldConfig(
            size_x=20,
            size_y=20,
            terrain_type="tavern",
            obstacles=[],
            environmental_effects=[]
        )

        return session

    def test_save_and_load_combat_session(self, mock_campaign_manager, combat_session):
        """Test saving and loading a combat session.

        Validates that combat flow updates persisted models correctly:
        - Session is saved to active/ directory
        - Load retrieves the saved session
        - All session data (combatants, round, turn order) persists correctly
        """
        campaign_id = "test_campaign_001"
        mock_campaign_manager.ensure_campaign_structure(campaign_id)

        # Initialize persistence manager
        persistence_manager = CombatPersistenceManager(mock_campaign_manager)

        # Save the session
        saved = persistence_manager.save_combat_session(campaign_id, combat_session)
        assert saved is True, "Combat session should save successfully"

        # Load the session (uses load_active_combat, not load_combat_session)
        loaded_session = persistence_manager.load_active_combat(campaign_id)

        # Verify loaded data matches original
        assert loaded_session is not None, "Should load the saved combat session"
        assert loaded_session.session_id == combat_session.session_id
        assert loaded_session.scene_id == combat_session.scene_id
        assert loaded_session.round_number == combat_session.round_number
        assert loaded_session.current_turn_index == combat_session.current_turn_index
        assert len(loaded_session.combatants) == len(combat_session.combatants)

        # Check combatant details (use hp not current_hp)
        for char_id, combatant in combat_session.combatants.items():
            loaded_combatant = loaded_session.combatants[char_id]
            assert loaded_combatant.name == combatant.name
            assert loaded_combatant.hp == combatant.hp
            assert loaded_combatant.max_hp == combatant.max_hp
            assert loaded_combatant.initiative == combatant.initiative
            assert loaded_combatant.is_npc == combatant.is_npc

    def test_combat_state_manager_persistence(self, mock_campaign_manager):
        """Test CombatStateManager persistence operations.

        Validates that CombatStateManager:
        - Creates combat sessions properly
        - Automatically saves to disk via persistence manager
        - Can recover sessions on restart
        """
        campaign_id = "test_campaign_002"
        mock_campaign_manager.ensure_campaign_structure(campaign_id)

        # Create test characters
        player = CharacterInfo(
            character_id="player_001",
            name="Thorin",
            character_class="Fighter",
            level=5,
            hit_points_current=45,
            hit_points_max=50,
            armor_class=18,
            character_type="player",
            voice_id="nathaniel"
        )

        enemy = CharacterInfo(
            character_id="enemy_001",
            name="Bandit",
            character_class="Thug",
            level=2,
            hit_points_current=20,
            hit_points_max=20,
            armor_class=14,
            character_type="npc",
            voice_id="caleb"
        )

        # Initialize state manager with combat
        state_manager = CombatStateManager(
            campaign_manager=mock_campaign_manager,
            turn_manager=None
        )

        # Initialize combat (should auto-save)
        combat_session = state_manager.initialize_combat(
            scene_id="tavern_brawl",
            characters=[player, enemy],
            campaign_id=campaign_id
        )

        assert combat_session is not None
        assert combat_session.status == CombatStatus.IN_PROGRESS
        assert len(combat_session.combatants) == 2

        # Create new state manager to simulate restart
        new_state_manager = CombatStateManager(
            campaign_manager=mock_campaign_manager,
            turn_manager=None,
            auto_recover=True
        )

        # Should auto-recover the active combat session
        assert len(new_state_manager.active_sessions) == 1
        recovered_session = list(new_state_manager.active_sessions.values())[0]
        assert recovered_session.session_id == combat_session.session_id
        assert recovered_session.scene_id == "tavern_brawl"
        assert len(recovered_session.combatants) == 2

    def test_recovery_after_crash(self, mock_campaign_manager, combat_session):
        """Test recovery of combat state after simulated crash.

        Validates that:
        - Persistence manager can recover all active combats after restart
        - Recovered sessions maintain their state
        """
        campaign_id = "test_campaign_003"
        mock_campaign_manager.ensure_campaign_structure(campaign_id)

        # Save initial state
        persistence_manager = CombatPersistenceManager(mock_campaign_manager)
        saved = persistence_manager.save_combat_session(campaign_id, combat_session)
        assert saved is True

        # Simulate crash and recovery with new persistence manager
        new_persistence_manager = CombatPersistenceManager(mock_campaign_manager)

        # Recover all active sessions
        recovered = new_persistence_manager.recover_active_sessions()

        # Should have recovered one session
        assert len(recovered) == 1
        assert campaign_id in recovered

        # Verify recovered session
        recovered_session = recovered[campaign_id]
        assert recovered_session is not None
        assert recovered_session.session_id == combat_session.session_id
        assert recovered_session.status == CombatStatus.IN_PROGRESS
        assert recovered_session.round_number == 2
        assert len(recovered_session.combatants) == 2

    def test_end_combat_archival(self, mock_campaign_manager, combat_session):
        """Test archiving combat when it ends.

        Validates that:
        - Completed combats are archived to history/
        - Active combat file is removed
        - Archived file contains complete combat data
        """
        campaign_id = "test_campaign_004"
        mock_campaign_manager.ensure_campaign_structure(campaign_id)

        persistence_manager = CombatPersistenceManager(mock_campaign_manager)

        # Save active combat
        saved = persistence_manager.save_combat_session(campaign_id, combat_session)
        assert saved is True

        # End combat and archive
        combat_session.status = CombatStatus.COMPLETED
        combat_session.updated_at = datetime.now()
        archived = persistence_manager.archive_completed_combat(campaign_id, combat_session)
        assert archived is True

        # Verify no active combat (load_active_combat returns None)
        loaded = persistence_manager.load_active_combat(campaign_id)
        assert loaded is None, "Active combat should be removed after archival"

        # Verify combat was archived
        history_dir = mock_campaign_manager.get_campaign_path(campaign_id) / "combat" / "history"
        archived_files = list(history_dir.glob("*.json"))
        assert len(archived_files) == 1

        # Verify archived file contains session data
        with open(archived_files[0], 'r') as f:
            archived_data = json.load(f)
        assert archived_data["session_id"] == combat_session.session_id
        assert archived_data["status"] == "completed"
        assert "_metadata" in archived_data
        assert "archived_at" in archived_data["_metadata"]

    def test_multiple_combat_sessions_recovery(self, mock_campaign_manager):
        """Test recovery with multiple campaigns having active combat.

        Validates that:
        - Multiple campaigns can each have active combat
        - Recovery works across all campaigns simultaneously
        - Each campaign's combat state is isolated
        """
        # Create multiple campaigns with combat
        campaigns = ["campaign_A", "campaign_B", "campaign_C"]

        persistence_manager = CombatPersistenceManager(mock_campaign_manager)

        # Create and save combat for each campaign
        for i, campaign_id in enumerate(campaigns):
            mock_campaign_manager.ensure_campaign_structure(campaign_id)

            # Create unique combat session for each
            session = CombatSession(
                session_id=f"combat_{campaign_id}",
                scene_id=f"scene_{i}",
                status=CombatStatus.IN_PROGRESS,
                round_number=i + 1,
                current_turn_index=0
            )

            saved = persistence_manager.save_combat_session(campaign_id, session)
            assert saved is True

        # Verify all campaigns have active combat
        for campaign_id in campaigns:
            loaded = persistence_manager.load_active_combat(campaign_id)
            assert loaded is not None, f"Campaign {campaign_id} should have active combat"

        # Recovery simulation - create new persistence manager
        recovery_manager = CombatPersistenceManager(mock_campaign_manager)

        # Recover all active sessions
        recovered = recovery_manager.recover_active_sessions()

        # Should have recovered all 3 campaigns
        assert len(recovered) == 3
        for i, campaign_id in enumerate(campaigns):
            assert campaign_id in recovered
            assert recovered[campaign_id].round_number == i + 1
            assert recovered[campaign_id].scene_id == f"scene_{i}"

    def test_state_manager_end_combat_removes_active_files(
        self,
        mock_campaign_manager,
        combat_session
    ):
        """CombatStateManager.end_combat should remove persisted active combat files."""
        campaign_id = "test_campaign_005"
        mock_campaign_manager.ensure_campaign_structure(campaign_id)

        persistence_manager = CombatPersistenceManager(mock_campaign_manager)
        assert persistence_manager.save_combat_session(campaign_id, combat_session) is True

        # Build state manager which will recover the saved session
        state_manager = CombatStateManager(
            campaign_manager=mock_campaign_manager,
            turn_manager=None
        )

        session = state_manager.get_active_combat(campaign_id)
        assert session is not None
        session_id = session.session_id

        summary = state_manager.end_combat(session_id, reason="players_defeat")
        assert summary["reason"] == "players_defeat"

        # Session should be removed from memory and mapping
        assert state_manager.get_session(session_id) is None
        assert session_id not in state_manager.session_campaign_map

        # Active combat file should have been removed
        active_file = (
            mock_campaign_manager.get_campaign_path(campaign_id)
            / "combat"
            / "active"
            / f"{session_id}.json"
        )
        assert not active_file.exists()

        # Persistence lookup should also return no active combat
        assert persistence_manager.load_active_combat(campaign_id) is None
