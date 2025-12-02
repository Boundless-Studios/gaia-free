"""Mock implementation of DungeonMaster agent for testing."""
import json
from typing import Optional

class MockDungeonMaster:
    """Mock DungeonMaster with preset responses for testing."""

    def __init__(self):
        self.name = "MockDungeonMaster"
        self.model = "fake-model"
        self.instructions = "Test DM instructions"
        self.tools = []
        self.handoff = ["MockEncounterRunner"]
        
        # Preset responses for different scenarios
        self.responses = {
            "start_campaign": {
                "narrative": "Welcome adventurers! You find yourselves in the bustling town of Testville.",
                "turn": {"current_player": "All", "phase": "roleplay"},
                "status": {"location": "Testville", "time": "Morning", "weather": "Clear"},
                "characters": [
                    {"name": "Mayor Testworth", "description": "A jovial halfling in fine clothes"},
                    {"name": "Guard Captain", "description": "A stern human warrior"}
                ]
            },
            "explore_dungeon": {
                "narrative": "You descend into the dark dungeon. Water drips from the ceiling.",
                "turn": {"current_player": "Party", "phase": "exploration"},
                "status": {"location": "Dungeon Level 1", "light": "Dim", "environment": "Damp"},
                "characters": []
            },
            "combat_start": {
                "narrative": "Goblins leap from the shadows! Roll for initiative!",
                "turn": {"current_player": "All", "phase": "initiative"},
                "status": {"location": "Dungeon", "encounter": "Goblin Ambush"},
                "characters": [
                    {"name": "Goblin 1", "hp": 7, "ac": 15},
                    {"name": "Goblin 2", "hp": 7, "ac": 15}
                ]
            }
        }
    
    def get_response(self, scenario: str = "default") -> str:
        """Get a preset response for the given scenario."""
        if scenario in self.responses:
            return json.dumps(self.responses[scenario])
        
        # Default response
        return json.dumps({
            "narrative": "The test continues in an expected manner.",
            "turn": {"current_player": "Players", "phase": "exploration"},
            "status": {"test": True},
            "characters": []
        })
    
    def should_handoff(self, user_input: str) -> Optional[str]:
        """Determine if handoff is needed based on input."""
        lower_input = user_input.lower()
        
        if any(word in lower_input for word in ["attack", "fight", "combat"]):
            return "MockEncounterRunner"
        
        return None