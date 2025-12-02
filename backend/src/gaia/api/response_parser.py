"""
Response Parser - Handles parsing AI responses into structured data
"""
import logging
from typing import Optional
from gaia.api.schemas.chat import StructuredGameData

logger = logging.getLogger(__name__)

class ResponseParser:
    """Handles parsing AI responses into structured data."""
    
    @staticmethod
    def parse_json_response(response_text: str) -> Optional[StructuredGameData]:
        """Try to parse the response as JSON first."""
        from gaia.utils.json_utils import safe_json_parse
        
        parsed_json = safe_json_parse(response_text)
        if parsed_json is not None:
            return StructuredGameData(
                narrative=parsed_json.get('narrative'),
                turn=parsed_json.get('turn'),
                status=parsed_json.get('status'),
                characters=parsed_json.get('characters'),
                player_options=parsed_json.get('player_options'),
                environmental_conditions=parsed_json.get('environmental_conditions'),
                immediate_threats=parsed_json.get('immediate_threats'),
                story_progression=parsed_json.get('story_progression')
            )
        
        return None

    @staticmethod
    def parse_structured_response(response_text: str) -> StructuredGameData:
        """Parse the AI response to extract structured data for different panels."""
        logger.info(f"Parsing response: {response_text[:200]}...")
        
        # Try to parse as JSON
        json_result = ResponseParser.parse_json_response(response_text)
        if json_result:
            logger.info("Successfully parsed as JSON structured response")
            return json_result
        
        # If JSON parsing fails, return empty structured data
        logger.info("JSON parsing failed, returning empty structured data")
        return StructuredGameData(
            narrative=None,
            turn=None,
            status=None,
            characters=None,
            player_options=None,
            environmental_conditions=None,
            immediate_threats=None,
            story_progression=None
        ) 