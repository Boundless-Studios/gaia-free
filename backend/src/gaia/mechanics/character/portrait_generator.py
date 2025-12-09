"""Character portrait generation service."""

import logging
from typing import Any, Dict, Optional

from gaia.infra.image.image_artifact_store import ImageStorageType
from gaia.models.character.character_info import CharacterInfo
from gaia_private.agents.generators.image_generator import ImageGeneratorAgent

logger = logging.getLogger(__name__)


class CharacterPortraitGenerator:
    """Generates character portraits using the existing ImageGenerator agent.

    Follows the run_without_tools pattern:
    - Build raw prompt from character metadata
    - ImageGenerator.generate() routes to run_without_tools() for portraits
    - enhance_prompt() refines the raw prompt using AI
    - generate_image_tool() creates the final image
    """

    def __init__(self):
        self.image_generator = ImageGeneratorAgent()

    async def generate_portrait(
        self,
        character_info: CharacterInfo,
        session_id: Optional[str] = None,
        custom_additions: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a portrait for a character.

        This method follows the ImageGeneratorAgent.run_without_tools() pattern:
        1. Build raw prompt from character metadata
        2. Call ImageGenerator.generate() with image_type="portrait"
        3. generate() routes portraits through run_without_tools()
        4. run_without_tools() uses enhance_prompt() to refine the prompt
        5. Finally calls generate_image_tool() to create the image

        Args:
            character_info: CharacterInfo object with visual metadata
            session_id: Campaign ID for session-scoped media
            custom_additions: Optional user-provided prompt additions

        Returns:
            Dict with success status, portrait URL, path, and metadata:
            {
                "success": True,
                "image_url": "file:///path/to/portrait.png",
                "local_path": "/path/to/portrait.png",
                "prompt": "Enhanced prompt used for generation",
                "type": "portrait",
                "style": "fantasy art",
                "original_prompt": "Raw prompt before enhancement",
                "service": "provider_name"
            }
        """
        # Build raw prompt from character metadata
        raw_prompt = self._build_portrait_prompt(character_info, custom_additions)

        logger.info(f"🎨 Generating portrait for {character_info.name}")
        logger.info(f"   Raw prompt: {raw_prompt[:100]}...")

        # Use existing ImageGenerator.generate() method
        # It automatically routes "portrait" type through run_without_tools()
        # which calls enhance_prompt() and then generate_image_tool()
        result = await self.image_generator.generate(
            prompt=raw_prompt,
            image_type=ImageStorageType.PORTRAIT.value,  # Routes to run_without_tools automatically
            style="fantasy art",
            session_id=session_id  # Pass session_id for proper storage scoping
        )

        if not result.get("success"):
            logger.error(f"❌ Portrait generation failed for {character_info.name}: {result.get('error')}")
            return result

        if session_id:
            if proxy := result.get("proxy_url"):
                logger.info(f"✅ Portrait persisted for {character_info.name} at {proxy}")
            else:
                logger.info(f"✅ Portrait generated for {character_info.name} (session={session_id})")
        else:
            logger.info(f"✅ Portrait generated locally for {character_info.name}")
            logger.info(f"   Path: {result.get('local_path')}")

        return result

    def _build_portrait_prompt(
        self,
        character_info: CharacterInfo,
        custom_additions: Optional[str] = None
    ) -> str:
        """
        Build raw prompt from character visual metadata.

        This raw prompt will be enhanced by ImageGeneratorAgent.enhance_prompt()
        which already has portrait-specific enhancement logic (lines 362-378).

        The enhance_prompt method expects a description covering:
        - Name, descriptor, gender, race, age, class
        - Facial expression, facial features
        - Armor/attire, distinguishing features
        - Head position/angle

        Returns:
            Comma-separated description string
        """
        parts = []

        # Name
        if character_info.name:
            parts.append(character_info.name)

        # Descriptor (from facial expression or personality)
        if character_info.facial_expression:
            parts.append(character_info.facial_expression.lower())

        # Gender
        if character_info.gender:
            parts.append(character_info.gender.lower())

        # Race
        if character_info.race:
            parts.append(character_info.race)

        # Age category
        if character_info.age_category:
            parts.append(character_info.age_category.lower())

        # Class
        if character_info.character_class:
            parts.append(character_info.character_class)

        # Facial expression (repeated for emphasis if important)
        if character_info.facial_expression:
            parts.append(f"{character_info.facial_expression.lower()} expression")

        # Facial features
        if character_info.facial_features:
            parts.append(character_info.facial_features)

        # Attire/Armor
        if character_info.attire:
            parts.append(f"wearing {character_info.attire}")

        # Distinguishing features
        if character_info.distinguishing_feature:
            parts.append(character_info.distinguishing_feature)

        # Head position/pose (for portraits, this is head position)
        if character_info.pose:
            parts.append(character_info.pose.lower())

        # Custom user additions
        if custom_additions:
            parts.append(custom_additions)

        # Join all parts into a comma-separated description
        # enhance_prompt() will refine this into an optimized prompt
        prompt = ", ".join(parts)

        return prompt
