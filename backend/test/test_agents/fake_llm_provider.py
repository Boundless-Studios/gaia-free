"""Fake LLM provider for deterministic testing."""
from typing import Dict, List, Optional, AsyncGenerator
import json
from dataclasses import dataclass

@dataclass
class FakeMessage:
    role: str
    content: str

class FakeLLMProvider:
    """Fake LLM provider that returns preset responses based on agent type."""
    
    def __init__(self):
        self.responses = {
            "dungeon_master": {
                "default": json.dumps({
                    "narrative": "You stand at the entrance of the ancient tomb. The air is thick with dust and mystery.",
                    "turn": {"current_player": "Player 1", "phase": "exploration"},
                    "status": {"location": "Tomb Entrance", "time": "Dawn"},
                    "characters": [{"name": "Guardian Spirit", "description": "A translucent figure watches from the shadows"}]
                }),
                "combat": json.dumps({
                    "narrative": "The goblin attacks with its rusty sword!",
                    "turn": {"current_player": "Goblin", "phase": "combat", "initiative_order": ["Player 1", "Goblin"]},
                    "status": {"combat_round": 1, "location": "Dungeon"},
                    "characters": [{"name": "Goblin", "hp": 7, "ac": 15}]
                })
            },
            "scenario_analyzer": {
                "default": "ANALYZE: This appears to be an exploration scenario. Recommending DungeonMaster for narrative continuation.",
                "combat": "ANALYZE: Combat detected. Recommending EncounterRunner for combat management.",
            },
            "encounter_runner": {
                "default": json.dumps({
                    "encounter": {
                        "name": "Ambush in the Forest",
                        "enemies": [{"name": "Bandit", "hp": 11, "ac": 12}],
                        "environment": "Forest path",
                        "phase": "surprise"
                    }
                })
            },
            "output_formatter": {
                "default": json.dumps({
                    "narrative": "The formatted story continues...",
                    "metadata": {"formatted": True}
                })
            }
        }
        
        self.call_history = []
        self.stream_responses = {}
    
    async def generate(self, messages: List[Dict], model: str = "fake-model", **kwargs) -> str:
        """Generate a response based on the agent type."""
        # Extract agent type from messages
        agent_type = self._extract_agent_type(messages)
        scenario_type = self._extract_scenario_type(messages)
        
        # Record the call
        self.call_history.append({
            "messages": messages,
            "model": model,
            "agent_type": agent_type,
            "scenario_type": scenario_type
        })
        
        # Return appropriate response
        if agent_type in self.responses:
            responses = self.responses[agent_type]
            if scenario_type in responses:
                return responses[scenario_type]
            return responses.get("default", "No response configured")
        
        return "Unknown agent type"
    
    async def generate_stream(self, messages: List[Dict], model: str = "fake-model", **kwargs) -> AsyncGenerator[str, None]:
        """Stream a response character by character."""
        response = await self.generate(messages, model, **kwargs)
        
        # Simulate streaming by yielding chunks
        chunk_size = 10
        for i in range(0, len(response), chunk_size):
            yield response[i:i+chunk_size]
    
    def _extract_agent_type(self, messages: List[Dict]) -> str:
        """Extract agent type from system message."""
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content", "").lower()
                if "dungeon master" in content:
                    return "dungeon_master"
                elif "scenario" in content and "analyzer" in content:
                    return "scenario_analyzer"
                elif "encounter" in content:
                    return "encounter_runner"
                elif "format" in content:
                    return "output_formatter"
        return "unknown"
    
    def _extract_scenario_type(self, messages: List[Dict]) -> str:
        """Extract scenario type from user message."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if any(word in content for word in ["attack", "combat", "fight", "battle"]):
                    return "combat"
                elif any(word in content for word in ["rule", "spell", "ability"]):
                    return "rules"
        return "default"
    
    def set_response(self, agent_type: str, scenario: str, response: str):
        """Set a custom response for testing."""
        if agent_type not in self.responses:
            self.responses[agent_type] = {}
        self.responses[agent_type][scenario] = response
    
    def get_call_history(self) -> List[Dict]:
        """Get the history of calls made to this provider."""
        return self.call_history
    
    def clear_history(self):
        """Clear call history."""
        self.call_history = []