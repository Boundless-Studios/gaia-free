import json
import re
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

def parse_json_string(json_str: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Parse a JSON string that might be wrapped in markdown code blocks or other formatting.
    
    Args:
        json_str: String that may contain JSON, or already parsed dict
        
    Returns:
        Parsed dictionary if successful, None if parsing fails
    """
    # If it's already a dict, return it
    if isinstance(json_str, dict):
        return json_str
    
    if not isinstance(json_str, str):
        logger.warning(f"Expected string or dict, got {type(json_str)}")
        return None
    
    # Remove markdown code block formatting if present
    cleaned_str = json_str.strip()
    
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', cleaned_str, re.DOTALL)
    if json_match:
        cleaned_str = json_match.group(1).strip()
    
    # Try to find JSON object in the string
    json_object_match = re.search(r'\{.*\}', cleaned_str, re.DOTALL)
    if json_object_match:
        cleaned_str = json_object_match.group(0)
    
    # Try multiple parsing strategies
    parsing_strategies = [
        # Strategy 1: Direct parsing
        lambda s: json.loads(s),
        # Strategy 2: Try to fix common issues
        lambda s: json.loads(re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', s)),
        # Strategy 3: Try to fix trailing commas
        lambda s: json.loads(re.sub(r',\s*}', '}', s)),
        # Strategy 4: Try to fix missing quotes around keys
        lambda s: json.loads(re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', re.sub(r',\s*}', '}', s))),
    ]
    
    for i, strategy in enumerate(parsing_strategies):
        try:
            parsed = strategy(cleaned_str)
            if isinstance(parsed, dict):
                logger.debug(f"Successfully parsed JSON using strategy {i + 1}")
                return parsed
            else:
                logger.warning(f"Parsed JSON is not a dictionary: {type(parsed)}")
                continue
        except json.JSONDecodeError as e:
            logger.debug(f"Strategy {i + 1} failed: {e}")
            continue
        except Exception as e:
            logger.debug(f"Strategy {i + 1} failed with unexpected error: {e}")
            continue
    
    logger.warning(f"All JSON parsing strategies failed")
    logger.debug(f"Attempted to parse: {cleaned_str[:200]}...")
    return None

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract and parse JSON from text that may contain other content.
    
    Args:
        text: Text that may contain JSON
        
    Returns:
        Parsed dictionary if successful, None if parsing fails
    """
    return parse_json_string(text)

def create_fallback_structure(content, source_name="unknown"):
    """
    Create a fallback structure when JSON parsing fails completely.
    
    Args:
        content: The original content that failed to parse
        source_name: Name of the source for logging
        
    Returns:
        A basic structured dictionary with the content
    """
    logger = logging.getLogger(__name__)
    logger.warning(f"Creating fallback structure for {source_name}")
    
    # Try to extract any meaningful text from the garbled content
    if isinstance(content, str):
        # Remove any obvious garbage characters
        cleaned = content.replace('\x00', '').replace('\xff', '').strip()
        # Take first 200 characters if it's too long
        if len(cleaned) > 200:
            cleaned = cleaned[:200] + "..."
    else:
        cleaned = str(content)[:200]
    
    return {
        "narrative": f"Scene description from {source_name}: {cleaned}",
        "turn": "It is the player's turn to act",
        "status": f"Processing response from {source_name}"
    }

def safe_json_parse(content):
    """
    Safely parse JSON content with multiple fallback strategies.
    
    Args:
        content: The content to parse
        
    Returns:
        Parsed JSON object or None if all attempts fail
    """
    logger = logging.getLogger(__name__)
    
    if content is None:
        return None
        
    if isinstance(content, dict):
        return content
        
    if not isinstance(content, str):
        logger.warning(f"Content is not a string: {type(content)}")
        return None
    
    # Clean control characters from content
    content = clean_control_characters(content)
    
    # Log the content for debugging
    content_preview = content[:200] + "..." if len(content) > 200 else content
    logger.info(f"Attempting to parse JSON: {content_preview}")
    
    strategies = [
        ("Direct JSON parse", lambda x: json.loads(x)),
        ("Strip whitespace", lambda x: json.loads(x.strip())),
        ("Extract JSON from text", lambda x: extract_json_from_text(x)),
        ("Parse JSON string", lambda x: parse_json_string(x)),
    ]
    
    for strategy_name, strategy_func in strategies:
        try:
            result = strategy_func(content)
            logger.info(f"JSON parsing succeeded with: {strategy_name}")
            return result
        except Exception as e:
            logger.warning(f"JSON parsing failed with {strategy_name}: {str(e)}")
    
    logger.error(f"All JSON parsing strategies failed")
    return None 

def clean_control_characters(text: str) -> str:
    """
    Remove control characters from text that can break JSON parsing.
    
    Args:
        text: Text to clean
        
    Returns:
        Cleaned text without control characters
    """
    # Remove all control characters except newline, tab, and carriage return
    cleaned = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
    return cleaned

def parse_json_with_fallbacks(data, max_attempts=3):
    """
    Attempt to parse JSON with multiple fallback strategies.
    
    Args:
        data: The data to parse (string, dict, or other)
        max_attempts: Maximum number of parsing attempts
        
    Returns:
        Parsed JSON object or None if all attempts fail
    """
    if data is None:
        logger.warning("❌ JSON parsing failed: data is None")
        return None
        
    if isinstance(data, dict):
        logger.info("✅ Data is already a dictionary, returning as-is")
        return data
        
    if not isinstance(data, str):
        logger.warning(f"❌ JSON parsing failed: data is not a string (type: {type(data)})")
        return None
    
    # Clean control characters from data
    data = clean_control_characters(data)
    
    # Log the actual content for debugging
    content_preview = data[:200] + "..." if len(data) > 200 else data
    logger.info(f"🔍 Attempting to parse JSON content: {content_preview}")
    
    strategies = [
        ("Direct JSON parse", lambda x: json.loads(x)),
        ("Strip whitespace", lambda x: json.loads(x.strip())),
        ("Extract JSON from text", lambda x: extract_json_from_text(x)),
        ("Parse JSON string", lambda x: parse_json_string(x)),
    ]
    
    for i, (strategy_name, strategy_func) in enumerate(strategies[:max_attempts]):
        try:
            result = strategy_func(data)
            logger.info(f"✅ JSON parsing succeeded with strategy: {strategy_name}")
            return result
        except Exception as e:
            logger.warning(f"❌ JSON parsing attempt {i+1} failed with strategy '{strategy_name}': {str(e)}")
            if i == len(strategies) - 1:  # Last attempt
                logger.error(f"💥 All JSON parsing strategies failed for content type: {type(data)}")
                logger.error(f"💥 Content preview: {content_preview}")
                logger.error(f"💥 Content length: {len(data)} characters")
    
    return None 
