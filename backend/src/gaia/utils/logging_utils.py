"""Common logging utilities for Gaia agents."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

# Get logger for this module
logger = logging.getLogger(__name__)

def log_tool_usage(tool_name: str, input_data: Dict[str, Any], agent_name: str, context: str = ""):
    """Log useful information about tool usage.
    
    Args:
        tool_name: Name of the tool being invoked
        input_data: Input parameters passed to the tool
        agent_name: Name of the agent invoking the tool
        context: Additional context information (e.g., conversation_id)
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "input_data": input_data,
        "context": context,
        "agent": agent_name
    }
    
    logger.info(f"Tool Usage: {json.dumps(log_entry, indent=2)}")
    
    # Also write to a dedicated tool usage log file
    try:
        # Get the logs directory relative to the project root
        logs_dir = Path(__file__).parent.parent.parent / "logs"
        logs_dir.mkdir(exist_ok=True)
        tool_log_file = logs_dir / "tool_usage.log"
        
        with open(tool_log_file, "a", encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write to tool usage log: {e}")

def create_logged_tool_handler(tool_name: str, agent_name: str, handler_func=None):
    """Create a logged tool handler that wraps the original handler with logging.
    
    Args:
        tool_name: Name of the tool
        agent_name: Name of the agent
        handler_func: Optional async function to call after logging
        
    Returns:
        Async function that logs tool usage and optionally calls the handler
    """
    async def logged_handler(ctx, input_data):
        """Logged tool handler wrapper."""
        # Safely extract context information from ToolContext
        context_info = "unknown"
        try:
            if hasattr(ctx, 'conversation_id'):
                context_info = ctx.conversation_id
            elif hasattr(ctx, 'get'):
                context_info = ctx.get('conversation_id', 'unknown')
            else:
                context_info = str(ctx)[:100]  # Use string representation if available
        except Exception:
            context_info = "unknown"
        
        log_tool_usage(tool_name, input_data, agent_name, f"Context: {context_info}")
        
        if handler_func:
            return await handler_func(ctx, input_data)
        else:
            # Default placeholder behavior
            return {"status": "logged", "tool": tool_name, "agent": agent_name}
    
    return logged_handler 