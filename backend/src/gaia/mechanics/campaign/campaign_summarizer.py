"""Campaign Summarizer - Handles periodic summarization and persistence of campaign data."""

import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from gaia_private.agents.utility.summarizer import SummarizerAgent
from gaia.infra.llm.agent_runner import AgentRunner
from gaia.infra.llm.model_manager import PreferredModels

logger = logging.getLogger(__name__)

# TODO Create a proper data class for campaign sumaries

class CampaignSummarizer:
    """Handles campaign summarization, merging, and persistence."""
    
    def __init__(self, campaign_manager):
        """Initialize the campaign summarizer.
        
        Args:
            campaign_manager: SimpleCampaignManager instance for accessing campaign data
        """
        self.campaign_manager = campaign_manager
        self.summarization_interval = 5  # Summarize every 5 turns
        
    def should_summarize(self, turn_number: int) -> bool:
        """Check if we should summarize based on turn number.
        
        Args:
            turn_number: Current turn number
            
        Returns:
            True if turn is a multiple of summarization_interval
        """
        return turn_number > 0 and turn_number % self.summarization_interval == 0
    
    def get_summary_path(self, campaign_id: str) -> Path:
        """Get the path to the summaries directory for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Path to campaign summaries directory
        """
        campaign_dir = self.campaign_manager._find_campaign_dir(campaign_id)
        if not campaign_dir:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        summary_dir = campaign_dir / "data" / "summaries"
        summary_dir.mkdir(parents=True, exist_ok=True)
        return summary_dir
    
    def load_latest_summary(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Load the most recent summary for a campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Latest summary dict or None if no summaries exist
        """
        try:
            summary_dir = self.get_summary_path(campaign_id)
            
            # Find all summary files
            summary_files = sorted(summary_dir.glob("summary_turn_*.json"))
            
            if not summary_files:
                logger.info(f"No existing summaries found for campaign {campaign_id}")
                return None
            
            # Load the most recent summary
            latest_file = summary_files[-1]
            with open(latest_file, 'r') as f:
                summary = json.load(f)
                logger.info(f"Loaded summary from {latest_file.name}")
                return summary
                
        except Exception as e:
            logger.error(f"Failed to load latest summary: {e}")
            return None
    
    def save_summary(self, campaign_id: str, summary: Dict[str, Any], turn_number: int) -> bool:
        """Save a summary to disk.
        
        Args:
            campaign_id: Campaign identifier
            summary: Summary data to save
            turn_number: Turn number for this summary
            
        Returns:
            True if saved successfully
        """
        try:
            summary_dir = self.get_summary_path(campaign_id)
            
            # Add metadata
            summary["metadata"] = {
                "turn_number": turn_number,
                "generated_at": datetime.now().isoformat(),
                "summarization_interval": self.summarization_interval
            }
            
            # Save with turn number in filename
            filename = summary_dir / f"summary_turn_{turn_number:04d}.json"
            with open(filename, 'w') as f:
                json.dump(summary, f, indent=2)
            
            logger.info(f"Saved summary to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return False
    
    def merge_summaries(self, old_summary: Dict[str, Any], new_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two summaries, deduplicating where necessary.
        
        Args:
            old_summary: Previous summary
            new_summary: New summary to merge
            
        Returns:
            Merged summary with deduplicated data
        """
        merged = {
            "summary": "",
            "characters": [],
            "locales": [],
            "events": [],
            "treasures": [],
            "story_threads": []
        }
        
        # Combine narrative summaries
        old_text = old_summary.get("summary", "")
        new_text = new_summary.get("summary", "")
        
        if old_text and new_text:
            merged["summary"] = f"{old_text}\n\n{new_text}"
        else:
            merged["summary"] = old_text or new_text
        
        # Merge and deduplicate characters by name
        character_map = {}
        for char in old_summary.get("characters", []):
            character_map[char["name"]] = char
        
        for char in new_summary.get("characters", []):
            name = char["name"]
            if name in character_map:
                # Update existing character with new info
                existing = character_map[name]
                # Prefer newer description if it's longer/more detailed
                if len(char.get("description", "")) > len(existing.get("description", "")):
                    character_map[name] = char
            else:
                character_map[name] = char
        
        merged["characters"] = list(character_map.values())
        
        # Merge and deduplicate locales by name
        locale_map = {}
        for locale in old_summary.get("locales", []):
            locale_map[locale["name"]] = locale
        
        for locale in new_summary.get("locales", []):
            name = locale["name"]
            if name not in locale_map:
                locale_map[name] = locale
        
        merged["locales"] = list(locale_map.values())
        
        # Combine events (usually don't deduplicate as events are unique)
        merged["events"] = old_summary.get("events", []) + new_summary.get("events", [])
        
        # Merge and deduplicate treasures by name
        treasure_map = {}
        for treasure in old_summary.get("treasures", []):
            treasure_map[treasure["name"]] = treasure
        
        for treasure in new_summary.get("treasures", []):
            name = treasure["name"]
            if name not in treasure_map:
                treasure_map[name] = treasure
        
        merged["treasures"] = list(treasure_map.values())
        
        # Merge story threads (deduplicate exact matches)
        thread_set = set()
        merged_threads = []

        for thread in old_summary.get("story_threads", []) + new_summary.get("story_threads", []):
            # Handle both string and dict formats
            if isinstance(thread, str):
                thread_text = thread
                thread_obj = {"thread": thread}
            elif isinstance(thread, dict):
                thread_text = thread.get("thread", "")
                thread_obj = thread
            else:
                # Skip invalid thread types
                logger.warning(f"Invalid thread type: {type(thread)}")
                continue

            if thread_text and thread_text not in thread_set:
                thread_set.add(thread_text)
                merged_threads.append(thread_obj)
        
        merged["story_threads"] = merged_threads
        
        return merged
    
    async def generate_summary(
        self, 
        campaign_id: str,
        last_n_messages: int = 0,
        merge_with_previous: bool = True,
        model: str = PreferredModels.KIMI.value
    ) -> Dict[str, Any]:
        """Generate a campaign summary from recent history.
        
        Args:
            campaign_id: Campaign identifier
            last_n_messages: Number of recent messages to summarize (0 for all)
            merge_with_previous: Whether to merge with previous summary
            model: Model to use for summarization
            
        Returns:
            Generated summary dict
        """
        # Load campaign history
        history = self.campaign_manager.load_campaign_history(campaign_id)
        
        if not history:
            logger.warning(f"No history found for campaign {campaign_id}")
            return {"summary": "No campaign history available", "characters": [], 
                    "locales": [], "events": [], "treasures": [], "story_threads": []}
        
        # Take last N messages or all
        if last_n_messages > 0:
            recent_history = history[-last_n_messages:]
        else:
            recent_history = history
        
        # Build prompt from history
        history_text = self._format_history_for_summary(recent_history)
        
        # Create summarizer
        summarizer = SummarizerAgent()
        summarizer.config.model = model
        await summarizer.ensure_prompt_loaded()
        agent = summarizer.as_openai_agent()
        
        prompt = f"""Please provide a COMPLETE and COMPREHENSIVE summary of this ENTIRE campaign from beginning to end.

IMPORTANT: This is the COMPLETE campaign history. Summarize EVERYTHING that has happened, not just recent events.

Campaign History ({len(recent_history)} messages):
{history_text}

You must include:
- A detailed narrative summary covering the ENTIRE story from beginning to current point
- ALL characters that have appeared (with their roles and descriptions)
- ALL locations visited or mentioned
- ALL major events in chronological order
- ALL treasures, items, or important objects
- ALL ongoing story threads and unresolved plots

Remember to return your response in the structured JSON format specified in your instructions."""
        
        logger.info(f"Generating summary for {campaign_id} from {len(recent_history)} messages")
        
        # Run summarizer
        result = await AgentRunner.run(
            agent=agent,
            prompt=prompt,
            model=model,
            temperature=0.5
        )
        
        # Extract and parse summary
        summary_text = AgentRunner.extract_text_response(result)
        
        if not summary_text:
            logger.error("Failed to generate summary")
            return {"summary": "Failed to generate summary", "characters": [], 
                    "locales": [], "events": [], "treasures": [], "story_threads": []}
        
        # Parse the summary
        summary = self._parse_summary_response(summary_text)
        
        # Merge with previous if requested
        if merge_with_previous:
            previous_summary = self.load_latest_summary(campaign_id)
            if previous_summary:
                logger.info("Merging with previous summary")
                summary = self.merge_summaries(previous_summary, summary)
        
        return summary
    
    def _format_history_for_summary(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history for the summarizer.
        
        Args:
            history: List of message dicts
            
        Returns:
            Formatted history text
        """
        formatted_messages = []
        
        for msg in history:
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            
            # Handle assistant messages that might be structured data
            if role == "ASSISTANT" and isinstance(content, dict):
                # Extract key narrative elements
                narrative = content.get("narrative", "")
                status = content.get("status", "")
                characters = content.get("characters", "")
                
                formatted_content = f"NARRATIVE: {narrative}"
                if status:
                    formatted_content += f"\nSTATUS: {status}"
                if characters:
                    formatted_content += f"\nCHARACTERS: {characters}"
                
                formatted_messages.append(f"{role}: {formatted_content}")
            else:
                # Regular message - don't truncate for complete summaries
                formatted_messages.append(f"{role}: {content}")
        
        return "\n\n".join(formatted_messages)
    
    def _parse_summary_response(self, summary_text: str) -> Dict[str, Any]:
        """Parse the summary response from the LLM.
        
        Args:
            summary_text: Raw text response from summarizer
            
        Returns:
            Parsed summary dict
        """
        try:
            # Check if JSON is wrapped in markdown code blocks
            if "```json" in summary_text:
                # Extract JSON from markdown
                start = summary_text.find("```json") + 7
                end = summary_text.find("```", start)
                if end > start:
                    json_text = summary_text[start:end].strip()
                    return json.loads(json_text)
            
            # Try direct JSON parsing
            return json.loads(summary_text)
            
        except json.JSONDecodeError:
            # If not valid JSON, return as plain text summary
            logger.warning("Summary is not valid JSON, returning as plain text")
            return {
                "summary": summary_text,
                "characters": [],
                "locales": [],
                "events": [],
                "treasures": [],
                "story_threads": []
            }
    
    async def summarize_after_turn(
        self,
        campaign_id: str,
        turn_number: int,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Generate and save a summary after a turn if needed.
        
        This should be called asynchronously after returning the response to the player.
        
        Args:
            campaign_id: Campaign identifier
            turn_number: Current turn number
            force: Force summarization regardless of interval
            
        Returns:
            Generated summary if summarization occurred, None otherwise
        """
        if not force and not self.should_summarize(turn_number):
            return None
        
        logger.info(f"Starting periodic summarization for campaign {campaign_id} at turn {turn_number}")
        
        try:
            # Calculate messages since last summary
            # Each turn has 2 messages (user + assistant), so messages = turns * 2
            last_summary_turn = turn_number - self.summarization_interval
            if last_summary_turn < 0:
                last_summary_turn = 0
            
            # Get messages since the last summary (or from beginning if first summary)
            turns_since_last = turn_number - last_summary_turn
            messages_since_last = turns_since_last * 2  # Each turn = 1 user message + 1 assistant message
            
            logger.info(f"Summarizing {turns_since_last} turns ({messages_since_last} messages) since turn {last_summary_turn}")
            
            summary = await self.generate_summary(
                campaign_id=campaign_id,
                last_n_messages=messages_since_last,
                merge_with_previous=True
            )
            
            # Save the summary
            if self.save_summary(campaign_id, summary, turn_number):
                logger.info(f"Successfully saved summary for turn {turn_number}")
                return summary
            else:
                logger.error(f"Failed to save summary for turn {turn_number}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to generate summary after turn {turn_number}: {e}")
            return None
    
    async def generate_one_time_summary(self, campaign_id: str) -> Dict[str, Any]:
        """Generate a complete one-time summary of the entire campaign.
        
        Args:
            campaign_id: Campaign identifier
            
        Returns:
            Complete campaign summary
        """
        logger.info(f"Generating complete one-time summary for campaign {campaign_id}")
        
        # Get campaign data to determine current turn
        campaign_data = self.campaign_manager.load_campaign(campaign_id)
        turn_number = 0
        if campaign_data:
            # Try to get turn number from campaign data
            turn_number = len(self.campaign_manager.load_campaign_history(campaign_id)) // 2  # Rough estimate
        
        # Generate summary of entire campaign
        summary = await self.generate_summary(
            campaign_id=campaign_id,
            last_n_messages=0,  # All messages
            merge_with_previous=False  # Fresh summary
        )
        
        # Save it
        if turn_number == 0:
            turn_number = 9999  # Special marker for complete summary
        
        self.save_summary(campaign_id, summary, turn_number)
        
        return summary
