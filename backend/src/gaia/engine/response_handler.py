"""Response handling and structured response processing for D&D campaigns."""

import logging
from typing import Optional, Dict, Any
from agents import Runner, RunConfig, ModelSettings
from agents.items import ItemHelpers

from gaia.utils.json_utils import safe_json_parse, create_fallback_structure
from gaia_private.agents.core.agent_configurations import DEFAULT_CONFIG, AgentRole
from gaia.infra.llm.model_manager import resolve_model, get_model_provider_for_resolved_model

logger = logging.getLogger(__name__)


class ResponseHandler:
    """Handles response processing and structured data extraction for D&D campaigns."""
    
    def __init__(self, orchestration_config=None):
        """Initialize ResponseHandler with optional orchestration configuration."""
        self.orchestration_config = orchestration_config or DEFAULT_CONFIG
    
    
    def extract_dm_response(self, dm_result) -> str:
        """Extract the text response from the DM agent result."""
        return ItemHelpers.text_message_outputs(dm_result.new_items)
    
    def extract_structured_data_from_result(self, result) -> Optional[Dict[str, Any]]:
        """Extract structured data from an agent result."""
        if not hasattr(result, 'final_output') or not result.final_output:
            return None
        
        output = result.final_output
        
        if hasattr(output, 'model_dump'):
            # It's a Pydantic model
            structured_data = output.model_dump()
            # Structured data logging removed - logged elsewhere
            return structured_data
        elif isinstance(output, dict):
            structured_data = output
            return structured_data
        elif isinstance(output, str):
            # Handle string output using common utility
            logger.debug(f"Agent returned string, attempting to parse JSON...")
            structured_data = safe_json_parse(output)
            if structured_data is None:
                logger.error(f"Failed to parse JSON from agent string output")
            else:
                logger.debug(f"Successfully parsed JSON from agent: {str(structured_data)[:100]}...")
            return structured_data
        
        return None
    
    def parse_structured_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse structured data from a response string."""
        return safe_json_parse(response)
    
    def is_properly_structured(self, data: Dict[str, Any]) -> bool:
        """Check if the data has the required structure for D&D responses."""
        required_fields = ["answer", "narrative", "turn", "status"]
        return all(field in data and data[field] for field in required_fields)
    
    def extract_answer(self, structured_data: Dict[str, Any]) -> Optional[str]:
        """Extract answer from various sources."""
        answer = structured_data.get("player_response", structured_data.get("turn","No answer available"))
    
        return answer
    
    def process_dm_result(self, dm_result, dm_response: str) -> Optional[Dict[str, Any]]:
        """Process the DM result to extract structured data"""
        dm_structured_data = None
        
        # Try to get structured output from the DM result
        dm_structured_data = self.extract_structured_data_from_result(dm_result)
        
        # If we didn't get structured data from DM, try to parse the response text
        if not dm_structured_data:
            dm_structured_data = self.parse_structured_response(dm_response)
        
        return dm_structured_data
    
    async def create_final_structured_data(self, dm_structured_data: Optional[Dict[str, Any]], 
                                         dm_response: str) -> Dict[str, Any]:
        """Create the final structured data using the best available source."""
        # Check if we already have properly structured data from the DM
        if dm_structured_data and self.is_properly_structured(dm_structured_data):
            logger.info("DM already returned properly structured data - using it directly")
            structured_data = dm_structured_data
        else:
            # Try to parse the original DM response as fallback
            logger.info("Trying to parse original DM response...")
            structured_data = self.parse_structured_response(dm_response)
            
            # Final fallback: create basic structure from DM response if all else fails
            if not structured_data:
                logger.warning("All parsing attempts failed, creating basic fallback structure")
                structured_data = create_fallback_structure(dm_response, "Dungeon Master response")
        
        return structured_data 
