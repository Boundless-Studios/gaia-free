"""Tests for internal/debug API endpoints."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any
import asyncio

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import the endpoints we're testing
from gaia.api.routes.internal import (
    router,
    get_scene_analyzer,
    get_context_manager,
    SceneAnalysisRequest,
    SceneAnalysisResponse
)


class TestInternalEndpoints:
    """Test internal API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client for the router."""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)

        # Override the auth dependency to bypass authentication in tests
        async def mock_admin():
            return {"user_id": "test_admin", "is_admin": True}

        # Import and patch the dependency
        from gaia.api.routes import internal as internal_endpoints
        if internal_endpoints.AUTH_AVAILABLE:
            # Override the get_admin_user dependency
            app.dependency_overrides[internal_endpoints.get_admin_user] = mock_admin

        return TestClient(app)
    
    @pytest.fixture
    def mock_scene_analyzer(self):
        """Mock scene analyzer."""
        with patch('gaia.api.routes.internal.ParallelSceneAnalyzer') as mock:
            analyzer = Mock()
            analyzer.analyze_scene = AsyncMock(return_value={
                "analysis_timestamp": "2025-08-18T00:00:00",
                "execution_time_seconds": 1.0,
                "complexity": {
                    "level": "SIMPLE",
                    "score": 2,
                    "factors": [],
                    "primary_challenge": "Test challenge",
                    "requires_multi_agent": False
                },
                "requirements": {
                    "tools": ["dice_roller"],
                    "agents": ["DungeonMaster"],
                    "tool_justifications": {},
                    "agent_justifications": {},
                    "priority_order": ["DungeonMaster"],
                    "parallel_capable": False
                },
                "scene": {
                    "primary_type": "COMBAT",
                    "secondary_types": [],
                    "game_phase": "INITIATIVE",
                    "environment": {},
                    "participants": {},
                    "stakes_level": "MEDIUM",
                    "time_sensitive": False
                },
                "special_considerations": {
                    "flags": [],
                    "rule_clarifications_needed": [],
                    "continuity_checks": [],
                    "balance_concerns": [],
                    "player_abilities_relevant": [],
                    "environmental_modifiers": [],
                    "requires_dm_judgment": False,
                    "safety_considerations": [],
                    "edge_case_detected": False
                },
                "routing": {
                    "primary_agent": "DungeonMaster",
                    "confidence": "HIGH",
                    "reasoning": "Simple combat scenario",
                    "alternatives": [],
                    "handoff_context": {},
                    "agent_sequence": ["DungeonMaster"],
                    "routing_complexity": "SIMPLE",
                    "special_instructions": ""
                },
                "overall": {
                    "confidence_score": 0.9,
                    "recommended_approach": "SINGLE_AGENT_RESPONSE",
                    "warnings": [],
                    "optimizations": []
                }
            })
            mock.return_value = analyzer
            yield analyzer
    
    @pytest.fixture
    def mock_context_manager(self):
        """Mock context manager."""
        with patch('gaia.api.routes.internal.ContextManager') as mock:
            manager = Mock()
            manager.get_analysis_context = Mock(return_value={
                "current_input": "test input",
                "previous_scenes": [],
                "last_user_actions": [],
                "game_state": {},
                "active_characters": [],
                "campaign_metadata": {
                    "campaign_id": "test_campaign",
                    "title": "Test Campaign"
                },
                "timestamp": "2025-08-18T00:00:00"
            })
            mock.return_value = manager
            yield manager
    
    @pytest.mark.asyncio
    async def test_analyze_scene_endpoint(self, client, mock_scene_analyzer):
        """Test the scene analysis endpoint."""
        with patch('gaia.api.routes.internal.get_scene_analyzer', return_value=mock_scene_analyzer):
            with patch('gaia.api.routes.internal.resolve_model', return_value="llama3.1:8b"):
                response = client.post(
                    "/api/internal/analyze-scene",
                    json={
                        "user_input": "I attack the goblin",
                        "model": "llama3.1:8b",
                        "include_previous_scenes": False
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "analysis" in data
                assert data["model_used"] == "llama3.1:8b"
                assert data["execution_time"] == 1.0
    
    @pytest.mark.asyncio
    async def test_analyze_scene_with_context(self, client, mock_scene_analyzer, mock_context_manager):
        """Test scene analysis with campaign context."""
        with patch('gaia.api.routes.internal.get_scene_analyzer', return_value=mock_scene_analyzer):
            with patch('gaia.api.routes.internal.get_context_manager', return_value=mock_context_manager):
                with patch('gaia.api.routes.internal.resolve_model', return_value="llama3.1:8b"):
                    response = client.post(
                        "/api/internal/analyze-scene",
                        json={
                            "user_input": "I search for traps",
                            "campaign_id": "test_campaign",
                            "model": "llama3.1:8b",
                            "include_previous_scenes": True,
                            "num_previous_scenes": 2
                        }
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    mock_context_manager.get_analysis_context.assert_called()
    
    def test_get_analyzer_status(self, client):
        """Test getting analyzer status."""
        response = client.get("/api/internal/scene-analyzer/status")
        
        assert response.status_code == 200
        data = response.json()
        assert "initialized" in data
        assert "model" in data
        assert "analyzers" in data
    
    @pytest.mark.asyncio
    async def test_test_individual_analyzer(self, client, mock_scene_analyzer):
        """Test individual analyzer testing endpoint."""
        mock_analyzer = Mock()
        mock_analyzer.analyze = AsyncMock(return_value={
            "complexity_level": "SIMPLE",
            "complexity_score": 2,
            "factors": [],
            "primary_challenge": "None",
            "requires_multi_agent": False
        })

        mock_scene_analyzer.complexity_analyzer = mock_analyzer

        with patch('gaia.api.routes.internal.get_scene_analyzer', return_value=mock_scene_analyzer):
            with patch('gaia.api.routes.internal.resolve_model', return_value="llama3.1:8b"):
                response = client.post(
                    "/api/internal/test-individual-analyzer",
                    params={
                        "analyzer_name": "complexity",
                        "user_input": "I attack",
                        "model": "llama3.1:8b"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["analyzer"] == "complexity"
                assert "result" in data
    
    def test_internal_health_check(self, client):
        """Test internal health check endpoint."""
        response = client.get("/api/internal/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["component"] == "internal_api"
    
    @pytest.mark.asyncio
    async def test_get_campaign_context(self, client, mock_context_manager):
        """Test getting campaign context."""
        with patch('gaia.api.routes.internal.get_context_manager', return_value=mock_context_manager):
            response = client.get("/api/internal/campaign/test_campaign/context")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["campaign_id"] == "test_campaign"
            assert "context" in data
    
    @pytest.mark.asyncio
    async def test_get_campaign_context_with_summary(self, client, mock_context_manager):
        """Test getting campaign context with summary."""
        # Mock context manager to return context with summary
        mock_context_manager.get_analysis_context = Mock(return_value={
            "current_input": "",
            "previous_scenes": [],
            "last_user_actions": [],
            "game_state": {},
            "active_characters": [],
            "campaign_metadata": {
                "campaign_id": "test_campaign",
                "title": "Test Campaign"
            },
            "summary": {
                "summary": "Test summary",
                "characters": [],
                "locales": [],
                "events": [],
                "treasures": [],
                "story_threads": []
            },
            "timestamp": "2025-08-18T00:00:00"
        })

        with patch('gaia.api.routes.internal.get_context_manager', return_value=mock_context_manager):
            response = client.get(
                "/api/internal/campaign/test_campaign/context?include_summary=true"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "context" in data
            mock_context_manager.get_analysis_context.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_summarize_campaign(self, client):
        """Test campaign summarization endpoint."""
        mock_summary = {
            "summary": "The party entered a dungeon",
            "characters": [{"name": "Hero", "description": "Brave warrior"}],
            "locales": [{"name": "Dark Dungeon", "description": "Mysterious underground complex"}],
            "events": [],
            "treasures": [],
            "story_threads": []
        }

        with patch('gaia.api.routes.internal.CampaignSummarizer') as mock_summarizer_class:
            mock_summarizer = Mock()
            mock_summarizer.generate_summary = AsyncMock(return_value=mock_summary)
            mock_summarizer_class.return_value = mock_summarizer

            response = client.post(
                "/api/internal/campaign/test_campaign/summarize?last_n_messages=10"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "summary" in data
            assert data["campaign_id"] == "test_campaign"
            assert data["characters_found"] == 1
            mock_summarizer.generate_summary.assert_called_once()
    
    def test_analyze_scene_error_handling(self, client):
        """Test error handling in scene analysis."""
        with patch('gaia.api.routes.internal.get_scene_analyzer') as mock_get_analyzer:
            mock_get_analyzer.side_effect = Exception("Test error")

            # Also need to mock model resolution to avoid API key errors
            with patch('gaia.api.routes.internal.resolve_model') as mock_resolve:
                mock_resolve.return_value = "claude-3-5-sonnet-20241022"

                response = client.post(
                    "/api/internal/analyze-scene",
                    json={
                        "user_input": "test",
                        "model": "claude-3-5-sonnet-20241022"
                    }
                )

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is False
                assert "error" in data
                assert "Test error" in data["error"]
    
    def test_invalid_analyzer_name(self, client):
        """Test invalid analyzer name in individual test."""
        # Mock model resolution to avoid API key requirements
        with patch('gaia.api.routes.internal.resolve_model') as mock_resolve:
            mock_resolve.return_value = "claude-3-5-sonnet-20241022"

            response = client.post(
                "/api/internal/test-individual-analyzer",
                params={
                    "analyzer_name": "invalid_analyzer",
                    "user_input": "test",
                    "model": "claude-3-5-sonnet-20241022"
                }
            )

            assert response.status_code == 400
            assert "Unknown analyzer" in response.json()["detail"]


class TestSceneAnalysisModels:
    """Test Pydantic models for scene analysis."""
    
    def test_scene_analysis_request_model(self):
        """Test SceneAnalysisRequest model."""
        request = SceneAnalysisRequest(
            user_input="I attack",
            campaign_id="test_campaign",
            model="llama3.1:8b",
            context={"test": "context"},
            include_previous_scenes=True,
            num_previous_scenes=3
        )
        
        assert request.user_input == "I attack"
        assert request.campaign_id == "test_campaign"
        assert request.model == "llama3.1:8b"
        assert request.context == {"test": "context"}
        assert request.include_previous_scenes is True
        assert request.num_previous_scenes == 3
    
    def test_scene_analysis_response_model(self):
        """Test SceneAnalysisResponse model."""
        response = SceneAnalysisResponse(
            success=True,
            analysis={"test": "analysis"},
            error=None,
            execution_time=1.5,
            model_used="llama3.1:8b"
        )
        
        assert response.success is True
        assert response.analysis == {"test": "analysis"}
        assert response.error is None
        assert response.execution_time == 1.5
        assert response.model_used == "llama3.1:8b"