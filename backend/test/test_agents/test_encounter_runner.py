"""Mock implementation of EncounterRunner agent for testing."""
import json

class MockEncounterRunner:
    """Mock EncounterRunner with preset responses for testing."""

    def __init__(self):
        self.name = "MockEncounterRunner"
        self.model = "fake-model"
        self.instructions = "Test encounter runner instructions"
        self.tools = []
        self.handoff = []
    
    def get_response(self, scenario: str) -> str:
        """Get response for different scenarios."""
        responses = {
            "combat_start": json.dumps({
                "message": "Combat initiated! Roll for initiative.",
                "encounter_type": "combat",
                "phase": "initiative"
            }),
            "default": json.dumps({
                "message": "Encounter runner response",
                "encounter_type": "general"
            })
        }
        
        return responses.get(scenario, responses["default"]) 