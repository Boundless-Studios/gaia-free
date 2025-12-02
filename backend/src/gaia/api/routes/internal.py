"""Internal and debug API endpoints for testing and development.

This module provides internal/debug endpoints for testing scene analyzers,
campaign summarization, and other development utilities.

Key Endpoints:
    POST /api/internal/test/scene-analyzer - Test individual scene analyzer
    POST /api/internal/test/scene-analysis - Test parallel scene analysis
    POST /api/internal/campaign/{id}/regenerate-summary - Regenerate summaries
    GET /api/internal/campaign/{id}/context - Get campaign context

Authentication:
    - Uses auth middleware when available (optional dependency)
    - Falls back to no-op authentication when auth module not installed
    - Tests can override authentication via dependency injection

Dependencies:
    ParallelSceneAnalyzer: For scene analysis endpoints
    ContextManager: For campaign context retrieval
    CampaignSummarizer: For summary regeneration
    Orchestrator: For agent handoff testing

Recent Updates:
    - Added proper HTTPException re-raising (Oct 2025)
    - Fixed exception handling to preserve FastAPI error responses
    - All 12 endpoint tests now passing with auth fallback
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os

from gaia_private.agents.scene_analyzer.parallel_scene_analyzer import ParallelSceneAnalyzer
from gaia_private.session.context_manager import ContextManager
from gaia_private.session.history_manager import ConversationHistoryManager
from gaia_private.orchestration.orchestrator import Orchestrator
from gaia.infra.llm.model_manager import resolve_model, ModelName, PreferredModels
from gaia.mechanics.campaign.campaign_summarizer import CampaignSummarizer  # Still needed for other endpoints

logger = logging.getLogger(__name__)

# Import authentication if available
try:
    # Setup shared imports for auth and db submodules
    from .. import shared_imports
    from fastapi import Depends as FastAPIDepends
    from auth.src.middleware import get_admin_user, get_optional_user
    AUTH_AVAILABLE = True
except ImportError:
    logger.warning("Auth module not available, using dummy authentication")
    AUTH_AVAILABLE = False
    
    # Dummy functions when auth is not available
    async def get_admin_user():
        return None
    
    async def get_optional_user():
        return None

# Create admin-only dependency
def require_admin():
    """Dependency that requires admin authentication."""
    if not AUTH_AVAILABLE:
        return lambda: None  # No-op when auth is disabled
    return FastAPIDepends(get_admin_user)

def optional_auth():
    """Dependency for optional authentication."""
    if not AUTH_AVAILABLE:
        return lambda: None  # No-op when auth is disabled
    return FastAPIDepends(get_optional_user)

# Create router for internal endpoints
router = APIRouter(prefix="/api/internal", tags=["internal"])

# Global instances (will be initialized on first use)
_scene_analyzer: Optional[ParallelSceneAnalyzer] = None
_context_manager: Optional[ContextManager] = None


def get_orchestrator() -> Orchestrator:
    """Get the singleton orchestrator instance."""
    return Orchestrator()


class SceneAnalysisRequest(BaseModel):
    """Request model for scene analysis."""
    user_input: str
    campaign_id: Optional[str] = None
    model: Optional[str] = ModelName.DEEPSEEK_3_1.value
    context: Optional[Dict[str, Any]] = None
    include_previous_scenes: bool = True
    num_previous_scenes: int = 2


class SceneAnalysisResponse(BaseModel):
    """Response model for scene analysis."""
    success: bool
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    model_used: Optional[str] = None


def get_scene_analyzer(model: str = "llama3.2:3b") -> ParallelSceneAnalyzer:
    """Get or create the scene analyzer instance."""
    global _scene_analyzer
    if _scene_analyzer is None or _scene_analyzer.complexity_analyzer.model != model:
        logger.info(f"Initializing ParallelSceneAnalyzer with model: {model}")
        _scene_analyzer = ParallelSceneAnalyzer(model=model, context_manager=get_context_manager())
    return _scene_analyzer


def get_context_manager() -> ContextManager:
    """Get or create the context manager instance."""
    global _context_manager
    if _context_manager is None:
        logger.info("Initializing ContextManager")
        history_manager = ConversationHistoryManager()
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        _context_manager = ContextManager(history_manager, campaign_manager)
    return _context_manager


@router.post("/analyze-scene", response_model=SceneAnalysisResponse)
async def analyze_scene(
    request: SceneAnalysisRequest,
    admin_user = require_admin()
) -> SceneAnalysisResponse:
    """Admin only - 
    Analyze a scene using the parallel scene analyzer.
    
    This endpoint runs all 5 scene analyzers in parallel and returns
    comprehensive analysis including complexity, scene type, routing
    recommendations, and special considerations.
    """
    try:
        # Resolve the model to ensure it's available
        resolved_model = resolve_model(request.model or ModelName.DEEPSEEK_3_1.value)
        logger.info(f"Analyzing scene with model: {resolved_model}")
        
        # Get or create analyzer
        analyzer = get_scene_analyzer(resolved_model)
        
        # Prepare context
        context = request.context or {}
        
        # If campaign_id is provided and include_previous_scenes is True,
        # enrich context with campaign data
        if request.campaign_id and request.include_previous_scenes:
            try:
                context_manager = get_context_manager()
                rich_context = context_manager.get_analysis_context(
                    request.user_input,
                    request.campaign_id,
                    request.num_previous_scenes
                )
                context.update(rich_context)
                logger.info(f"Enriched context with campaign data from {request.campaign_id}")
            except Exception as e:
                logger.warning(f"Failed to enrich context: {e}")
        
        # Run analysis
        logger.info(f"Running scene analysis for: {request.user_input[:100]}...")
        result = await analyzer.analyze_scene(
            request.user_input,
            context,
            request.campaign_id
        )
        
        return SceneAnalysisResponse(
            success=True,
            analysis=result,
            execution_time=result.get("execution_time_seconds"),
            model_used=resolved_model
        )
        
    except Exception as e:
        logger.error(f"Scene analysis failed: {e}", exc_info=True)
        return SceneAnalysisResponse(
            success=False,
            error=str(e)
        )


@router.get("/scene-analyzer/status")
async def get_analyzer_status(
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - Get the status of the scene analyzer."""
    global _scene_analyzer
    
    if _scene_analyzer is None:
        return {
            "initialized": False,
            "model": None,
            "analyzers": []
        }
    
    return {
        "initialized": True,
        "model": _scene_analyzer.complexity_analyzer.model,
        "analyzers": [
            "ComplexityAnalyzer",
            "ToolSelector", 
            "SceneCategorizer",
            "SpecialConsiderations",
            "NextAgentRecommender"
        ],
        "context_manager_available": _scene_analyzer.context_manager is not None
    }


@router.post("/test-individual-analyzer")
async def test_individual_analyzer(
    analyzer_name: str,
    user_input: str,
    model: str = "llama3.2:3b",
    context: Optional[Dict[str, Any]] = None,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Test an individual analyzer directly.
    
    Available analyzers:
    - complexity
    - tools
    - categorization
    - special
    - routing
    """
    try:
        resolved_model = resolve_model(model)
        analyzer = get_scene_analyzer(resolved_model)
        
        # Map analyzer names to actual analyzer instances
        analyzer_map = {
            "complexity": analyzer.complexity_analyzer,
            "tools": analyzer.tool_selector,
            "categorization": analyzer.scene_categorizer,
            "special": analyzer.special_considerations,
            "routing": analyzer.next_agent_recommender
        }
        
        if analyzer_name not in analyzer_map:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown analyzer: {analyzer_name}. Available: {list(analyzer_map.keys())}"
            )
        
        selected_analyzer = analyzer_map[analyzer_name]
        result = await selected_analyzer.analyze(user_input, context)
        
        return {
            "success": True,
            "analyzer": analyzer_name,
            "result": result,
            "model_used": resolved_model
        }

    except HTTPException:
        # Re-raise HTTPExceptions so FastAPI handles them properly
        raise
    except Exception as e:
        logger.error(f"Individual analyzer test failed: {e}", exc_info=True)
        return {
            "success": False,
            "analyzer": analyzer_name,
            "error": str(e)
        }


@router.get("/debug/last-analysis")
async def get_last_analysis(
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Get debug information about the last scene analysis performed.
    
    This is useful for debugging why certain routing decisions were made.
    """
    # This would need to store the last analysis result in memory
    # For now, return a placeholder
    return {
        "message": "Last analysis tracking not yet implemented",
        "hint": "Use /api/internal/analyze-scene to perform a new analysis"
    }


class RunCampaignRequest(BaseModel):
    """Request model for running a campaign turn."""
    user_input: str
    campaign_id: Optional[str] = None


class RunCampaignResponse(BaseModel):
    """Response model for campaign run."""
    success: bool
    campaign_id: Optional[str] = None
    response: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/run-campaign", response_model=RunCampaignResponse)
async def run_campaign_turn(
    request: RunCampaignRequest,
    admin_user = require_admin()
) -> RunCampaignResponse:
    """Admin only - 
    Run a campaign turn directly through the orchestrator.
    
    This endpoint tests the refactored architecture where:
    - Orchestrator manages campaign setup
    - CampaignRunner owns all agents and executes turns
    """
    try:
        logger.info(f"🎮 [INTERNAL] Running campaign turn")
        logger.info(f"  User input: {request.user_input[:100]}...")
        logger.info(f"  Campaign ID: {request.campaign_id}")
        
        # Get orchestrator singleton
        orchestrator = get_orchestrator()
        
        # Run the campaign
        result = await orchestrator.run_campaign(
            user_input=request.user_input,
            campaign_id=request.campaign_id
        )
        
        logger.info(f"✅ Campaign turn completed successfully")
        
        return RunCampaignResponse(
            success=True,
            campaign_id=result.get("campaign_id"),
            response=result
        )
        
    except Exception as e:
        logger.error(f"❌ Error running campaign turn: {e}", exc_info=True)
        return RunCampaignResponse(
            success=False,
            error=str(e)
        )


class TestTurnRequest(BaseModel):
    """Request model for testing a turn without persistence."""
    user_input: str
    campaign_id: Optional[str] = "test_campaign"


class TestTurnResponse(BaseModel):
    """Response model for test turn."""
    success: bool
    response: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/test-turn", response_model=TestTurnResponse)
async def test_turn_without_persistence(
    request: TestTurnRequest,
    admin_user = require_admin()
) -> TestTurnResponse:
    """Admin only - 
    Test a single turn execution without persisting any data.
    
    This endpoint uses the actual campaign_runner from the orchestrator
    to test the full end-to-end generation pipeline without saving anything.
    
    Perfect for testing changes to agents, routing logic, or response formatting.
    """
    try:
        logger.info(f"🧪 [TEST] Running test turn: {request.user_input[:100]}...")
        
        # Get the orchestrator and its campaign_runner
        orchestrator = get_orchestrator()
        
        # Run the turn directly
        result = await orchestrator.campaign_runner.run_turn(
            user_input=request.user_input,
            campaign_id=request.campaign_id or "test_campaign"
        )
        
        # Extract analysis from the smart router
        analysis = orchestrator.campaign_runner.smart_router.last_parallel_analysis
        
        return TestTurnResponse(
            success=True,
            response=result,
            analysis=analysis
        )
        
    except Exception as e:
        logger.error(f"❌ Error in test turn: {e}", exc_info=True)
        return TestTurnResponse(
            success=False,
            error=str(e)
        )


@router.get("/health")
async def internal_health_check() -> Dict[str, str]:
    """Internal health check endpoint."""
    return {
        "status": "healthy",
        "component": "internal_api"
    }


@router.get("/campaign/{campaign_id}/context")
async def get_campaign_context(
    campaign_id: str,
    num_scenes: int = 5,
    include_summary: bool = False,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Get the current context for a campaign.
    
    This includes:
    - Previous scenes
    - Recent user actions
    - Game state
    - Active characters
    - Campaign metadata
    - Optional: Campaign summary
    """
    try:
        context_manager = get_context_manager()
        
        # Get context with optional summary (now handled internally by ContextManager)
        context = context_manager.get_analysis_context(
            user_input="",  # Empty for just context retrieval
            campaign_id=campaign_id,
            num_scenes=num_scenes,
            include_summary=include_summary  # Pass the flag to ContextManager
        )
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "context": context
        }
        
    except Exception as e:
        logger.error(f"Failed to get campaign context: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


@router.post("/campaign/{campaign_id}/summarize")
async def summarize_campaign(
    campaign_id: str,
    last_n_messages: int = 50,
    model: str = "llama3.1:8b",
    merge_with_previous: bool = False,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Generate a summary of the campaign.
    
    This creates a structured summary using the CampaignSummarizer class:
    - Overall narrative summary
    - Characters encountered
    - Locations visited
    - Key events
    - Treasures found
    - Ongoing story threads
    
    Args:
        campaign_id: Campaign identifier
        last_n_messages: Number of recent messages to summarize (0 for all)
        model: LLM model to use for summarization
        merge_with_previous: Whether to merge with previous summaries
        
    Returns:
        Campaign summary with metadata
    """
    try:
        # Get orchestrator and campaign manager
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        
        # Create summarizer
        summarizer = CampaignSummarizer(campaign_manager)
        
        logger.info(f"Generating campaign summary for {campaign_id} using {model}")
        
        # Generate summary using CampaignSummarizer
        summary = await summarizer.generate_summary(
            campaign_id=campaign_id,
            last_n_messages=last_n_messages,
            merge_with_previous=merge_with_previous,
            model=model
        )
        
        # Calculate messages analyzed
        messages_analyzed = last_n_messages
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "summary": summary,
            "model_used": model,
            "messages_analyzed": messages_analyzed,
            "characters_found": len(summary.get("characters", [])),
            "locations_found": len(summary.get("locales", [])),
            "events_found": len(summary.get("events", [])),
            "treasures_found": len(summary.get("treasures", [])),
            "story_threads_found": len(summary.get("story_threads", []))
        }
            
    except Exception as e:
        logger.error(f"Campaign summarization failed: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


@router.post("/campaign/{campaign_id}/analyze-current-scene")
async def analyze_current_scene(
    campaign_id: str,
    model: str = "llama3.2:3b",
    num_previous_scenes: int = 3,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Analyze the current scene in a campaign using ParallelSceneAnalyzer.
    
    This endpoint:
    - Loads the latest user input from campaign history
    - Automatically includes campaign context and previous scenes
    - Runs all 5 scene analyzers in parallel
    - Returns comprehensive analysis for routing decisions
    
    Args:
        campaign_id: Campaign identifier
        model: LLM model to use for analysis
        num_previous_scenes: Number of previous scenes to include for context
        
    Returns:
        Scene analysis with routing recommendations
    """
    try:
        # Get orchestrator and campaign manager
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        
        # Load campaign history to find last user input
        history = campaign_manager.load_campaign_history(campaign_id)
        if not history:
            return {
                "success": False,
                "error": f"No history found for campaign {campaign_id}"
            }
        
        # Find the last user input
        last_user_input = None
        for message in reversed(history):
            if message.get("role") == "user":
                last_user_input = message.get("content", "")
                break
        
        if not last_user_input:
            return {
                "success": False,
                "error": "No user input found in campaign history"
            }
        
        # Setup analyzer with resolved model
        resolved_model = resolve_model(model)
        analyzer = get_scene_analyzer(resolved_model)
        
        # Get enriched context
        context_manager = get_context_manager()
        context = context_manager.get_analysis_context(
            last_user_input,
            campaign_id,
            num_previous_scenes
        )
        
        # Run analysis using ParallelSceneAnalyzer directly
        logger.info(f"Analyzing scene for campaign {campaign_id}: {last_user_input[:100]}...")
        result = await analyzer.analyze_scene(
            last_user_input,
            context,
            campaign_id
        )
        
        # The ParallelSceneAnalyzer already returns a complete analysis
        # Just return it directly with minimal wrapper
        return {
            "success": True,
            "campaign_id": campaign_id,
            "input_analyzed": last_user_input,
            "analysis": result,
            "model_used": resolved_model
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze current scene: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


@router.get("/campaign/{campaign_id}/current-status")
async def get_current_campaign_status(
    campaign_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Get the current status of a campaign including latest scene and context.
    
    This is useful for understanding what the analyzer will see.
    
    Args:
        campaign_id: Campaign identifier
        
    Returns:
        Current campaign status and latest scene information
    """
    try:
        # Get orchestrator and campaign manager
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        
        # Load campaign history
        history = campaign_manager.load_campaign_history(campaign_id)
        if not history:
            return {
                "success": False,
                "error": f"No history found for campaign {campaign_id}"
            }
        
        # Get last user and assistant messages
        last_user_msg = None
        last_assistant_msg = None
        
        for message in reversed(history):
            if not last_user_msg and message.get("role") == "user":
                last_user_msg = message
            elif not last_assistant_msg and message.get("role") == "assistant":
                last_assistant_msg = message
            if last_user_msg and last_assistant_msg:
                break
        
        # Get context
        context_manager = get_context_manager()
        user_input = last_user_msg.get("content", "") if last_user_msg else ""
        context = context_manager.get_analysis_context(user_input, campaign_id, 2)
        
        # Extract key information
        status = {
            "campaign_id": campaign_id,
            "total_messages": len(history),
            "total_turns": len(history) // 2,
            "last_user_input": last_user_msg.get("content", "N/A") if last_user_msg else "N/A",
            "last_user_timestamp": last_user_msg.get("timestamp", "N/A") if last_user_msg else "N/A",
            "last_assistant_response": {
                "narrative": last_assistant_msg.get("content", {}).get("narrative", "N/A")[:200] + "..." 
                    if isinstance(last_assistant_msg.get("content"), dict) else str(last_assistant_msg.get("content", "N/A"))[:200] + "..."
                    if last_assistant_msg else "N/A",
                "status": last_assistant_msg.get("content", {}).get("status", "N/A") 
                    if isinstance(last_assistant_msg.get("content"), dict) else "N/A"
                    if last_assistant_msg else "N/A"
            } if last_assistant_msg else {},
            "context_available": {
                "previous_scenes": len(context.get("previous_scenes", [])),
                "recent_actions": len(context.get("last_user_actions", [])),
                "active_characters": len(context.get("active_characters", [])),
                "game_state_fields": list(context.get("game_state", {}).keys())
            },
            "ready_for_analysis": bool(last_user_msg)
        }
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Failed to get campaign status: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


@router.post("/campaign/{campaign_id}/generate-complete-summary")
async def generate_complete_summary(
    campaign_id: str,
    model: str = PreferredModels.KIMI.value,
    save_to_disk: bool = True,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Admin only - 
    Generate a complete one-time summary of the entire campaign.
    
    This endpoint uses the CampaignSummarizer to create a comprehensive
    summary of ALL campaign history, not just recent messages.
    
    Args:
        campaign_id: Campaign identifier
        model: LLM model to use for summarization
        save_to_disk: Whether to save the summary to disk
        
    Returns:
        Complete campaign summary with metadata
    """
    try:
        # Get orchestrator and campaign manager
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        
        # Create summarizer
        summarizer = CampaignSummarizer(campaign_manager)
        
        # Check if campaign exists
        campaign_data = campaign_manager.load_campaign(campaign_id)
        if not campaign_data:
            return {
                "success": False,
                "error": f"Campaign {campaign_id} not found"
            }
        
        # Generate complete summary
        logger.info(f"Generating complete summary for campaign {campaign_id} using {model}")
        
        if save_to_disk:
            # Use generate_one_time_summary which saves automatically
            summary = await summarizer.generate_one_time_summary(campaign_id)
            summary_path = summarizer.get_summary_path(campaign_id)
            
            # Get the saved file name
            saved_files = sorted(summary_path.glob("summary_turn_*.json"))
            latest_file = saved_files[-1] if saved_files else None
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "summary": summary,
                "model_used": model,
                "saved_to": str(latest_file) if latest_file else None,
                "total_messages": len(campaign_manager.load_campaign_history(campaign_id)),
                "characters_found": len(summary.get("characters", [])),
                "locations_found": len(summary.get("locales", [])),
                "events_found": len(summary.get("events", [])),
                "treasures_found": len(summary.get("treasures", [])),
                "story_threads_found": len(summary.get("story_threads", []))
            }
        else:
            # Generate without saving
            summary = await summarizer.generate_summary(
                campaign_id=campaign_id,
                last_n_messages=0,  # All messages
                merge_with_previous=False,  # Fresh summary
                model=model
            )
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "summary": summary,
                "model_used": model,
                "saved_to": None,
                "total_messages": len(campaign_manager.load_campaign_history(campaign_id)),
                "characters_found": len(summary.get("characters", [])),
                "locations_found": len(summary.get("locales", [])),
                "events_found": len(summary.get("events", [])),
                "treasures_found": len(summary.get("treasures", [])),
                "story_threads_found": len(summary.get("story_threads", []))
            }
            
    except Exception as e:
        logger.error(f"Failed to generate complete summary: {e}", exc_info=True)
        return {
            "success": False,
            "campaign_id": campaign_id,
            "error": str(e)
        }


# Turn Management Endpoints

@router.get("/campaigns/{campaign_id}/current-turn")
async def get_current_turn(
    campaign_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get the current active turn for a campaign.
    
    Args:
        campaign_id: Campaign identifier
        
    Returns:
        Current turn information including available actions
    """
    try:
        orchestrator = get_orchestrator()
        turn_manager = orchestrator.campaign_runner.turn_manager
        
        # Get current turn
        turn = turn_manager.get_current_turn(campaign_id)
        
        if not turn:
            return {
                "success": False,
                "error": f"No active turn for campaign {campaign_id}"
            }
        
        return {
            "success": True,
            "turn": turn.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to get current turn: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/turns")
async def get_turn_history(
    campaign_id: str,
    limit: Optional[int] = 10,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get turn history for a campaign.
    
    Args:
        campaign_id: Campaign identifier
        limit: Maximum number of turns to return
        
    Returns:
        List of historical turns
    """
    try:
        orchestrator = get_orchestrator()
        turn_manager = orchestrator.campaign_runner.turn_manager
        
        # Get turn history
        turns = turn_manager.get_turn_history(campaign_id, limit)
        
        return {
            "success": True,
            "campaign_id": campaign_id,
            "turns": [turn.to_dict() for turn in turns],
            "total_count": len(turns)
        }
        
    except Exception as e:
        logger.error(f"Failed to get turn history: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/turns/{turn_id}")
async def get_turn_details(
    campaign_id: str,
    turn_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get details of a specific turn.
    
    Args:
        campaign_id: Campaign identifier
        turn_id: Turn identifier
        
    Returns:
        Turn details
    """
    try:
        orchestrator = get_orchestrator()
        campaign_manager = orchestrator.campaign_manager
        
        # Load specific turn
        turn_data = campaign_manager.load_turn(campaign_id, turn_id)
        
        if not turn_data:
            return {
                "success": False,
                "error": f"Turn {turn_id} not found in campaign {campaign_id}"
            }
        
        return {
            "success": True,
            "turn": turn_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get turn details: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/scenes")
async def get_campaign_scenes(
    campaign_id: str,
    limit: int = 10,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get recent scenes for a campaign.
    
    Args:
        campaign_id: Campaign identifier
        limit: Maximum number of scenes to return
        
    Returns:
        List of recent scenes
    """
    try:
        orchestrator = get_orchestrator()
        
        # Get scene manager from campaign runner
        scene_manager = orchestrator.campaign_runner.scene_integration.get_scene_manager(campaign_id)
        
        # Get recent scenes
        scenes = scene_manager.get_recent_scenes(limit)
        
        # Convert to dicts for JSON response
        scene_dicts = [scene.to_dict() for scene in scenes]
        
        return {
            "success": True,
            "scenes": scene_dicts,
            "count": len(scene_dicts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get scenes: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/scenes/{scene_id}")
async def get_scene_details(
    campaign_id: str,
    scene_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get details of a specific scene.
    
    Args:
        campaign_id: Campaign identifier
        scene_id: Scene identifier
        
    Returns:
        Scene details
    """
    try:
        orchestrator = get_orchestrator()
        
        # Get scene manager
        scene_manager = orchestrator.campaign_runner.scene_integration.get_scene_manager(campaign_id)
        
        # Get specific scene
        scene = scene_manager.get_scene(scene_id)
        
        if not scene:
            return {
                "success": False,
                "error": f"Scene {scene_id} not found in campaign {campaign_id}"
            }
        
        return {
            "success": True,
            "scene": scene.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to get scene details: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/scenes/by-location/{location_id}")
async def get_scenes_by_location(
    campaign_id: str,
    location_id: str,
    limit: int = 10,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get scenes that occurred at a specific location.
    
    Args:
        campaign_id: Campaign identifier
        location_id: Location identifier
        limit: Maximum number of scenes to return
        
    Returns:
        List of scenes at the location
    """
    try:
        orchestrator = get_orchestrator()
        
        # Get scene manager
        scene_manager = orchestrator.campaign_runner.scene_integration.get_scene_manager(campaign_id)
        
        # Get scenes by location
        scenes = scene_manager.get_scenes_by_location(location_id, limit)
        
        # Convert to dicts
        scene_dicts = [scene.to_dict() for scene in scenes]
        
        return {
            "success": True,
            "location": location_id,
            "scenes": scene_dicts,
            "count": len(scene_dicts)
        }
        
    except Exception as e:
        logger.error(f"Failed to get scenes by location: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/campaigns/{campaign_id}/current-scene")
async def get_current_scene(
    campaign_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Get the current scene for a campaign.
    
    Args:
        campaign_id: Campaign identifier
        
    Returns:
        Current scene information
    """
    try:
        orchestrator = get_orchestrator()
        
        # Get current scene from scene integration
        current_scene = orchestrator.campaign_runner.scene_integration.current_scenes.get(campaign_id)
        
        if not current_scene:
            # Try to get the most recent scene
            scene_manager = orchestrator.campaign_runner.scene_integration.get_scene_manager(campaign_id)
            recent_scenes = scene_manager.get_recent_scenes(1)
            
            if recent_scenes:
                current_scene = recent_scenes[0].to_dict()
            else:
                return {
                    "success": True,
                    "current_scene": None,
                    "message": "No scenes found for this campaign"
                }
        
        return {
            "success": True,
            "current_scene": current_scene
        }
        
    except Exception as e:
        logger.error(f"Failed to get current scene: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


class ExecuteActionRequest(BaseModel):
    """Request model for executing a turn action."""
    action_id: str
    parameters: Optional[Dict[str, Any]] = None


@router.post("/campaigns/{campaign_id}/turns/execute")
async def execute_turn_action(
    campaign_id: str,
    request: ExecuteActionRequest,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Execute an action for the current turn.
    
    Args:
        campaign_id: Campaign identifier
        request: Action execution request
        
    Returns:
        Turn result with success/failure and state changes
    """
    try:
        orchestrator = get_orchestrator()
        turn_manager = orchestrator.campaign_runner.turn_manager
        
        # Get current turn
        turn = turn_manager.get_current_turn(campaign_id)
        if not turn:
            return {
                "success": False,
                "error": f"No active turn for campaign {campaign_id}"
            }
        
        # Find the action
        action = None
        for available_action in turn.available_actions:
            if available_action.action_id == request.action_id:
                action = available_action
                break
        
        if not action:
            return {
                "success": False,
                "error": f"Action {request.action_id} not available for current turn"
            }
        
        # Execute the action
        result = turn_manager.execute_action(turn, action, request.parameters)
        
        # Complete the turn after execution
        turn_manager.complete_turn(turn, result)
        
        return {
            "success": result.success,
            "turn_id": turn.turn_id,
            "message": result.message,
            "state_changes": result.state_changes
        }
        
    except Exception as e:
        logger.error(f"Failed to execute turn action: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/campaigns/{campaign_id}/turns/pass")
async def pass_turn(
    campaign_id: str,
    admin_user = require_admin()
) -> Dict[str, Any]:
    """Pass the current turn without taking an action.
    
    Args:
        campaign_id: Campaign identifier
        
    Returns:
        Success status and new turn information
    """
    try:
        orchestrator = get_orchestrator()
        turn_manager = orchestrator.campaign_runner.turn_manager
        
        # Get current turn
        turn = turn_manager.get_current_turn(campaign_id)
        if not turn:
            return {
                "success": False,
                "error": f"No active turn for campaign {campaign_id}"
            }
        
        # Find pass action
        pass_action = None
        for action in turn.available_actions:
            if action.action_id == "pass":
                pass_action = action
                break
        
        if pass_action:
            # Execute pass action
            result = turn_manager.execute_action(turn, pass_action, None)
            turn_manager.complete_turn(turn, result)
        else:
            # Just complete the turn
            turn_manager.complete_turn(turn)
        
        # Create next turn
        # TODO: Get next character in initiative order
        next_character_id = "player_main"  # Default for now
        next_turn = turn_manager.create_turn(
            campaign_id=campaign_id,
            character_id=next_character_id,
            character_name="user"
        )
        turn_manager.start_turn(next_turn)
        
        return {
            "success": True,
            "completed_turn_id": turn.turn_id,
            "next_turn": next_turn.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to pass turn: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
