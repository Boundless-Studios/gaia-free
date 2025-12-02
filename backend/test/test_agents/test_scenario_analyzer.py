"""Mock implementation of ScenarioAnalyzer agent for testing."""
from typing import Dict, Optional

class MockScenarioAnalyzer:
    """Mock ScenarioAnalyzer with preset analysis for testing."""

    def __init__(self):
        self.name = "MockScenarioAnalyzer"
        self.model = "fake-model"
        self.instructions = "Test analyzer instructions"
        self.tools = []
        self.handoff = []
        
        # Preset analysis patterns
        self.analysis_patterns = {
            "combat": {
                "complexity_score": 7,
                "reasoning": "Combat scenario detected",
                "scene_type": "combat",
                "game_style_recommendation": "tactical",
                "special_considerations": ["initiative", "turn order"],
                "player_intent": "Engage in combat",
                "dm_approach": "Use encounter runner for tactical combat",
                "recommended_agent": "MockEncounterRunner"
            },
            "rules": {
                "complexity_score": 5,
                "reasoning": "Rule clarification needed",
                "scene_type": "mixed",
                "game_style_recommendation": "balanced",
                "special_considerations": ["rule lookup"],
                "player_intent": "Understand game mechanics",
                "dm_approach": "Use rule enforcer for clarification"
            },
            "narrative": {
                "complexity_score": 3,
                "reasoning": "Narrative interaction",
                "scene_type": "social",
                "game_style_recommendation": "narrative",
                "special_considerations": [],
                "player_intent": "Roleplay and story",
                "dm_approach": "Use dungeon master for narrative",
                "recommended_agent": "MockDungeonMaster"
            }
        }
    
    def analyze(self, user_input: str) -> Dict:
        """Analyze user input and return recommendations."""
        lower_input = user_input.lower()
        
        # Determine analysis type based on keywords
        if any(word in lower_input for word in ["attack", "fight", "combat", "initiative"]):
            analysis = self.analysis_patterns["combat"]
        elif any(word in lower_input for word in ["rule", "how does", "can i", "mechanic"]):
            analysis = self.analysis_patterns["rules"]
        else:
            analysis = self.analysis_patterns["narrative"]
        
        return analysis
    
    def should_handoff(self, user_input: str) -> Optional[str]:
        """Determine if handoff is needed based on input."""
        analysis = self.analyze(user_input)
        return analysis.get("recommended_agent") 