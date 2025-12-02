"""
Tests for the Campaign Persistence Agent and Compaction Manager.
"""

import asyncio
import pytest
from typing import Dict, Any
from unittest.mock import MagicMock

from gaia_private.agents.utility.campaign_persistence_agent import CampaignPersistenceAgent
from gaia_private.session.compaction_manager import CompactionManager


@pytest.mark.asyncio
async def test_compaction_manager_basic():
    """Test the CompactionManager with sample data."""
    # Create mock campaign manager
    mock_campaign_manager = MagicMock()
    mock_campaign_manager.load_campaign.return_value = []
    mock_campaign_manager.get_campaign_data_path.return_value = None
    
    # Create compaction manager
    compaction_manager = CompactionManager(mock_campaign_manager)
    compaction_manager.compaction_enabled = True
    
    # Sample logs
    test_logs = [
        {
            "turn": 1,
            "role": "user",
            "content": "I am Aldric, a human paladin. I enter the tavern."
        },
        {
            "turn": 1,
            "role": "assistant",
            "content": {
                "narrative": "The Prancing Pony tavern is dimly lit and filled with the smell of ale. The bartender, a stout dwarf named Thorin, looks up as you enter. 'Welcome, traveler!'",
                "structured_data": {
                    "characters": {
                        "aldric": {"name": "Aldric", "class": "Paladin", "race": "Human"}
                    },
                    "npcs": {
                        "thorin": {"name": "Thorin", "role": "Bartender", "race": "Dwarf"}
                    },
                    "location": "The Prancing Pony Tavern"
                }
            }
        }
    ]
    
    # Test compaction prompt creation
    context = compaction_manager._prepare_compaction_context(test_logs, None)
    prompt = compaction_manager._create_compaction_prompt(context)
    
    assert "Aldric" in prompt
    assert "Prancing Pony" in prompt
    
    return {"status": "success", "prompt_length": len(prompt)}


def test_summarize_existing_state():
    """Test the state summarization functionality."""
    # Create mock campaign manager
    mock_campaign_manager = MagicMock()
    compaction_manager = CompactionManager(mock_campaign_manager)
    
    # Test with empty state
    summary = compaction_manager._summarize_existing_state(None)
    assert summary == "This is a new campaign with no existing state."
    
    # Test with populated state
    existing_state = {
        "characters": {
            "char_001": {"name": "Aragorn"},
            "char_002": {"name": "Legolas"},
            "char_003": {"name": "Gimli"},
            "char_004": {"name": "Boromir"}
        },
        "npcs": {
            "npc_001": {},
            "npc_002": {},
            "npc_003": {}
        },
        "environments": {
            "env_001": {},
            "env_002": {}
        },
        "quests": {
            "quest_001": {"status": "active"},
            "quest_002": {"status": "completed"},
            "quest_003": {"status": "active"}
        },
        "current_scene_id": "scene_42"
    }
    
    summary = compaction_manager._summarize_existing_state(existing_state)
    
    # Verify summary contains expected information
    assert "Characters (4): Aragorn, Legolas, Gimli and more..." in summary
    assert "NPCs tracked: 3" in summary
    assert "Locations discovered: 2" in summary
    assert "Active quests: 2" in summary
    assert "Current scene: scene_42" in summary
    
    print(f"Summary:\n{summary}")


if __name__ == "__main__":
    # Run basic test
    print("Running basic test...")
    result = asyncio.run(test_compaction_manager_basic())
    print(f"Basic test result: {result}\n")
    
    # Run summarization test
    print("Running summarization test...")
    test_summarize_existing_state()