"""JSON sanitizer for cleaning malformed JSON from LLM outputs."""

import re
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def sanitize_json_string(json_str: str) -> str:
    """Sanitize a JSON string by removing/escaping control characters.

    Args:
        json_str: Raw JSON string that may contain control characters

    Returns:
        Cleaned JSON string
    """
    if not json_str:
        return json_str

    # First, try to identify if this is a broken JSON with embedded content
    # Pattern: JSON that ends prematurely with extra content after
    pattern = r'^(\{[^}]*"[^"]*"):.*?(Combat State:|combat_state).*?\}.*?(\{.*?\})$'
    match = re.search(pattern, json_str, re.DOTALL)
    if match:
        # Try to extract the main JSON and ignore the broken parts
        main_json = json_str[:json_str.rfind('}')+1]
        json_str = main_json

    # Remove any control characters (0x00-0x1F) except for \t, \n, \r which we'll escape
    # First, temporarily replace valid escaped sequences
    json_str = json_str.replace('\\n', '__ESCAPED_N__')
    json_str = json_str.replace('\\r', '__ESCAPED_R__')
    json_str = json_str.replace('\\t', '__ESCAPED_T__')
    json_str = json_str.replace('\\"', '__ESCAPED_QUOTE__')
    json_str = json_str.replace('\\\\', '__ESCAPED_BACKSLASH__')

    # Now handle actual control characters in string values
    # This regex finds strings and processes them
    def clean_string_value(match):
        string_content = match.group(1)
        # Replace actual newlines, tabs, etc. with escaped versions
        string_content = string_content.replace('\n', '\\n')
        string_content = string_content.replace('\r', '\\r')
        string_content = string_content.replace('\t', '\\t')
        # Remove other control characters
        string_content = ''.join(char for char in string_content if ord(char) >= 32 or char in ['\t'])
        return f'"{string_content}"'

    # Apply to all string values
    json_str = re.sub(r'"([^"]*)"', clean_string_value, json_str)

    # Restore the valid escaped sequences
    json_str = json_str.replace('__ESCAPED_N__', '\\n')
    json_str = json_str.replace('__ESCAPED_R__', '\\r')
    json_str = json_str.replace('__ESCAPED_T__', '\\t')
    json_str = json_str.replace('__ESCAPED_QUOTE__', '\\"')
    json_str = json_str.replace('__ESCAPED_BACKSLASH__', '\\\\')

    # Remove any trailing content after the last valid }
    # Find the last } that would close the JSON object
    brace_count = 0
    last_valid_pos = -1
    for i, char in enumerate(json_str):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                last_valid_pos = i
                break

    if last_valid_pos > -1:
        json_str = json_str[:last_valid_pos + 1]

    return json_str


def parse_json_safely(json_str: str, fallback: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Parse JSON string safely with sanitization and fallback.

    Args:
        json_str: JSON string to parse
        fallback: Fallback dictionary to return if parsing fails

    Returns:
        Parsed JSON as dictionary, or fallback if parsing fails
    """
    if not json_str:
        return fallback or {}

    try:
        # First attempt: parse as-is
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.debug(f"Initial JSON parse failed: {e}")

        try:
            # Second attempt: sanitize and parse
            sanitized = sanitize_json_string(json_str)
            return json.loads(sanitized)
        except json.JSONDecodeError as e2:
            logger.warning(f"JSON parse failed even after sanitization: {e2}")
            logger.debug(f"Original JSON: {json_str[:500]}...")
            logger.debug(f"Sanitized JSON: {sanitized[:500]}...")

            if fallback:
                logger.info("Using fallback response")
                return fallback
            raise


def extract_json_from_text(text: str) -> Optional[str]:
    """Extract JSON object from text that may contain additional content.

    Args:
        text: Text that may contain JSON along with other content

    Returns:
        Extracted JSON string or None
    """
    # Look for JSON object boundaries
    start_idx = text.find('{')
    if start_idx == -1:
        return None

    # Find matching closing brace
    brace_count = 0
    end_idx = -1

    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i
                break

    if end_idx > start_idx:
        return text[start_idx:end_idx + 1]

    return None