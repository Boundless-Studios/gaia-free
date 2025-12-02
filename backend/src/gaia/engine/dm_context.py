"""DM Context for enhanced Dungeon Master interactions."""

from dataclasses import dataclass
import json
from typing import Dict, Optional
from gaia.engine.game_configuration import GameConfiguration

@dataclass 
class DMContext:
    """Enhanced context passed from Analyzer to DM"""
    # Raw analysis output from ScenarioAnalyzer
    analysis_output: str
    
    # Additional context
    player_input: str
    campaign_state: Dict
    game_config: GameConfiguration
    scene_context: Optional[str] = None  # Scene context from scene manager
    conversation_context: Optional[str] = None  # Conversation context from context manager
    
    def to_prompt_context(self) -> str:
        """Convert context to natural language for DM prompt"""
        context = f"""
SCENARIO ANALYSIS:
{self.analysis_output}

GAME CONFIGURATION:
- Style: {self.game_config.style.value}
- Rule Strictness: {self.game_config.rule_strictness}
- Player Agency Level: {self.game_config.player_agency_level}
- Pace Preference: {self.game_config.pace_preference}
"""
        return context
    
    def create_enhanced_prompt(self, user_input: str) -> str:
        """Create an enhanced prompt for the DM agent."""
        # Start with conversation context if available
        prompt = self.conversation_context if self.conversation_context else ""
        
        # Add the base prompt using the raw analysis from DMContext
        prompt += f"""
{self.to_prompt_context()}

Player Input: {user_input}

DM GUIDANCE:
Based on the scenario analysis above, respond appropriately to the player's input.
Maintain {self.game_config.pace_preference} pacing throughout the scene.
Focus on the player's intent and use the recommended approach from the analysis."""

        # Add scene context if available
        if self.scene_context:
            prompt += f"""

SCENE CONTEXT:
{self.scene_context}

Use this scene context to maintain consistency and reference previous locations, characters, and events that have been established."""

        return prompt 

    def get_conversation_context(self) -> str:
        """Return the latest conversation context string for streaming workflows."""
        if isinstance(self.conversation_context, str) and self.conversation_context.strip():
            return self.conversation_context

        history = []
        campaign_history = (self.campaign_state or {}).get("history")
        if isinstance(campaign_history, list):
            for message in campaign_history:
                role = message.get("role", "unknown")
                content = message.get("content", "")
                if isinstance(content, (dict, list)):
                    try:
                        content_str = json.dumps(content, ensure_ascii=False)
                    except Exception:
                        content_str = str(content)
                else:
                    content_str = str(content)
                history.append(f"{role}: {content_str}")

        if history:
            return "\n".join(history)

        # Fallback to the enhanced prompt so streaming has at least a minimal context
        return self.create_enhanced_prompt(self.player_input)
