"""
Active Player Options Agent - generates direct action suggestions for the turn-taking player.

This agent uses the 'active_player_options' prompt which is action-oriented and
generates options based on observable events from the previous player's turn.

This is used for the PRIMARY player (turn-taker) while PlayerOptionsAgent is used
for SECONDARY players (observers) with a more passive/discovery-focused prompt.
"""

import logging
import json
from typing import Dict, Any, Optional, List

from agents import Agent
from gaia.infra.llm.agent_runner import AgentRunner
from gaia.infra.llm.model_manager import ModelName

logger = logging.getLogger(__name__)


# Fallback prompt in case database is unavailable
FALLBACK_SYSTEM_PROMPT = """You are a player options generator for a D&D-style roleplaying game.

WHAT JUST HAPPENED (Observable):
{{current_char_name}} just acted, and here's what happened:
{{scene_narrative}}

NEXT PLAYER TO ACT: {{next_char_name}}
{{character_context}}

CRITICAL - OBSERVABLE INFORMATION ONLY:
You are generating options for {{next_char_name}} based on what they can OBSERVE.

INCLUDE options based on:
- What {{current_char_name}} just said or did (public actions)
- How the environment changed from {{current_char_name}}'s action
- What {{next_char_name}} can see, hear, smell, or perceive RIGHT NOW
- NPCs' reactions to {{current_char_name}}
- {{next_char_name}}'s personality/class influencing how they interpret what they observe

DO NOT include options based on:
- {{next_char_name}}'s private thoughts or internal knowledge
- {{current_char_name}}'s unspoken motivations
- Information {{next_char_name}} couldn't have observed
- Future events or outcomes {{next_char_name}} can't predict

YOUR JOB:
Generate 3-5 contextual action suggestions for {{next_char_name}}.

GUIDELINES:
- Frame options from {{next_char_name}}'s perspective, based on what they just witnessed
- Mix different action types (investigate, interact, move, speak, use ability)
- Consider {{next_char_name}}'s personality - bold/cautious, friendly/suspicious, etc.
- Consider {{next_char_name}}'s class - different classes notice different opportunities
- Keep options concise but evocative (5-10 words each)
- Options should respond to or build on what {{current_char_name}} just did
- Avoid generic options like "Do nothing" or "Wait"

RESPOND WITH JSON:
{
    "player_options": ["Action 1", "Action 2", "Action 3", "Action 4", "Action 5"]
}"""


class ActivePlayerOptionsAgent:
    """
    Agent for generating action-oriented options for the active turn-taking player.

    Uses the 'active_player_options' prompt from the database, which generates
    direct action suggestions based on what the previous player did.

    Template variables:
    - {{scene_narrative}}: What just happened in the scene
    - {{current_char_name}}: Name of the character who just acted
    - {{next_char_name}}: Name of the character who will act next (turn-taker)
    - {{character_context}}: Context about the next character's abilities/personality
    """

    # Agent identification for prompt loading
    agent_type = "active_player_options"
    prompt_key = "system_prompt"
    log_name = "ActivePlayerOptions"

    def __init__(self, model: str = None):
        """
        Initialize the ActivePlayerOptionsAgent.

        Args:
            model: Optional model override. Defaults to DEEPSEEK_3_1.
        """
        self.model = model or ModelName.DEEPSEEK_3_1.value
        self._prompt_cache: Optional[str] = None
        self._db_session = None

    async def _get_system_prompt(self, template_vars: Optional[Dict[str, Any]] = None) -> str:
        """
        Load the system prompt from database with optional template variable resolution.

        Args:
            template_vars: Optional dict of template variables to resolve

        Returns:
            The system prompt text with variables resolved
        """
        try:
            # Try to load from database using PromptService
            from gaia_private.prompts.prompt_service import PromptService
            from db.src import db_manager

            async with db_manager.get_async_session() as session:
                prompt_service = PromptService(session)
                prompt_text = await prompt_service.get_prompt_with_fallback(
                    agent_type=self.agent_type,
                    prompt_key=self.prompt_key,
                    fallback=FALLBACK_SYSTEM_PROMPT
                )

                # Resolve template variables if provided
                if template_vars:
                    prompt_text = await prompt_service.resolve_template(
                        prompt_text,
                        template_vars
                    )

                return prompt_text

        except ImportError:
            logger.warning(
                f"[{self.log_name}] gaia_private not available, using fallback prompt"
            )
            return self._resolve_fallback_prompt(template_vars)
        except Exception as e:
            logger.warning(
                f"[{self.log_name}] Failed to load prompt from database: {e}, using fallback"
            )
            return self._resolve_fallback_prompt(template_vars)

    def _resolve_fallback_prompt(self, template_vars: Optional[Dict[str, Any]] = None) -> str:
        """Resolve template variables in the fallback prompt."""
        prompt = FALLBACK_SYSTEM_PROMPT
        if template_vars:
            for key, value in template_vars.items():
                placeholder = "{{" + key + "}}"
                prompt = prompt.replace(placeholder, str(value) if value else "")
        return prompt

    async def generate_options(
        self,
        scene_narrative: str,
        current_char_name: str,
        next_char_name: str,
        character_context: str = "",
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate action options for the active turn-taking player.

        Args:
            scene_narrative: What just happened in the scene
            current_char_name: Name of the character who just acted
            next_char_name: Name of the character whose turn it is
            character_context: Additional context about the next character
            model: Optional model override

        Returns:
            Dict with 'player_options' key containing list of option strings
        """
        template_vars = {
            "scene_narrative": scene_narrative,
            "current_char_name": current_char_name,
            "next_char_name": next_char_name,
            "character_context": character_context or f"Playing as {next_char_name}"
        }

        try:
            # Get the resolved system prompt
            system_prompt = await self._get_system_prompt(template_vars)

            # Create agent with the resolved prompt
            agent = Agent(
                name=self.log_name,
                instructions=system_prompt,
                model=model or self.model,
            )

            # Run the agent
            user_prompt = f"""Based on what {current_char_name} just did, generate 3-5 action options for {next_char_name}.

Scene: {scene_narrative}

Remember to generate options that {next_char_name} could realistically take based on what they observed."""

            result = await AgentRunner.run(
                agent=agent,
                prompt=user_prompt,
                model=model or self.model,
                temperature=0.7,
            )

            # Extract the response
            response_text = AgentRunner.extract_text_response(result)

            if response_text:
                return self._parse_options_response(response_text)
            else:
                logger.warning(f"[{self.log_name}] No response text from agent")
                return {"player_options": []}

        except Exception as e:
            logger.error(f"[{self.log_name}] Error generating options: {e}")
            return {"player_options": []}

    def _parse_options_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the agent's response to extract player options.

        Args:
            response_text: Raw response from the agent

        Returns:
            Dict with 'player_options' key
        """
        try:
            # Try to parse as JSON
            if '{' in response_text and '}' in response_text:
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                json_str = response_text[start:end]
                parsed = json.loads(json_str)

                if isinstance(parsed, dict) and "player_options" in parsed:
                    options = parsed["player_options"]
                    if isinstance(options, list):
                        return {"player_options": options}

            # Fallback: try to extract numbered or bulleted options
            options = self._extract_options_from_text(response_text)
            return {"player_options": options}

        except json.JSONDecodeError as e:
            logger.warning(f"[{self.log_name}] JSON parse error: {e}")
            options = self._extract_options_from_text(response_text)
            return {"player_options": options}

    def _extract_options_from_text(self, text: str) -> List[str]:
        """
        Extract options from non-JSON text (numbered lists, bullets, etc).

        Args:
            text: Raw text to parse

        Returns:
            List of option strings
        """
        import re
        options = []

        # Try numbered list (1. Option, 1) Option, etc.)
        numbered_pattern = r'^\s*\d+[\.\)]\s*(.+)$'
        for line in text.split('\n'):
            match = re.match(numbered_pattern, line.strip())
            if match:
                option = match.group(1).strip().strip('"\'')
                if option and len(option) > 5:  # Filter out very short strings
                    options.append(option)

        if options:
            return options[:5]  # Max 5 options

        # Try bullet points
        bullet_pattern = r'^\s*[-•*]\s*(.+)$'
        for line in text.split('\n'):
            match = re.match(bullet_pattern, line.strip())
            if match:
                option = match.group(1).strip().strip('"\'')
                if option and len(option) > 5:
                    options.append(option)

        return options[:5] if options else []
