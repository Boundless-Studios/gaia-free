"""Mock orchestrator for testing agent interactions."""
from typing import Dict, List, Optional, AsyncGenerator
import json
import asyncio

class MockOrchestrator:
    """Mock orchestrator that uses test agents."""
    
    def __init__(self, llm_provider):
        self.llm_provider = llm_provider
        self.conversation_history = []
        self.agent_call_history = []
        self.current_agent = "TestScenarioAnalyzer"
        
        # Initialize test agents
        from test.test_agents.test_dungeon_master import TestDungeonMaster
        from test.test_agents.test_scenario_analyzer import TestScenarioAnalyzer
        from test.test_agents.test_encounter_runner import TestEncounterRunner
        
        self.agents = {
            "TestDungeonMaster": TestDungeonMaster(),
            "TestScenarioAnalyzer": TestScenarioAnalyzer(),
            "TestEncounterRunner": TestEncounterRunner()
        }
    
    async def run(self, user_input: str, campaign_id: Optional[str] = None) -> Dict:
        """Process user input through mock orchestrator."""
        # Add to history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # Check if agents exist
        if not self.agents:
            return {
                "response": {"message": "No suitable agent found"},
                "agent_used": "None",
                "analysis": {},
                "campaign_id": campaign_id
            }
        
        # Analyze with scenario analyzer
        if "TestScenarioAnalyzer" not in self.agents:
            return {
                "response": {"message": "No suitable agent found"},
                "agent_used": "None",
                "analysis": {},
                "campaign_id": campaign_id
            }
        
        analyzer = self.agents["TestScenarioAnalyzer"]
        analysis = analyzer.analyze(user_input)
        
        # Record agent call
        self.agent_call_history.append({
            "agent": "TestScenarioAnalyzer",
            "input": user_input,
            "output": analysis
        })
        
        # Get recommended agent
        recommended_agent = analysis["recommended_agent"]
        
        # Get response from recommended agent
        if recommended_agent in self.agents:
            agent = self.agents[recommended_agent]
            
            # Determine scenario for DM
            if recommended_agent == "TestDungeonMaster":
                scenario = self._determine_scenario(user_input)
                response = agent.get_response(scenario)
            elif recommended_agent == "TestEncounterRunner":
                scenario = self._determine_scenario(user_input)
                response = agent.get_response(scenario)
            else:
                response = json.dumps({"message": f"Response from {recommended_agent}"})
            
            # Record agent call
            self.agent_call_history.append({
                "agent": recommended_agent,
                "input": user_input,
                "output": response
            })
            
            # Parse response
            try:
                parsed_response = json.loads(response)
            except:
                parsed_response = {"message": response}
            
            return {
                "response": parsed_response,
                "agent_used": recommended_agent,
                "analysis": analysis,
                "campaign_id": campaign_id
            }
        
        # Default response
        return {
            "response": {"message": "No suitable agent found"},
            "agent_used": "None",
            "analysis": analysis,
            "campaign_id": campaign_id
        }
    
    async def run_stream(self, user_input: str, campaign_id: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Stream response for testing."""
        response = await self.run(user_input, campaign_id)
        response_str = json.dumps(response)
        
        # Simulate streaming
        chunk_size = 10
        for i in range(0, len(response_str), chunk_size):
            yield response_str[i:i+chunk_size]
            await asyncio.sleep(0.01)  # Small delay to simulate streaming
    
    def _determine_scenario(self, user_input: str) -> str:
        """Determine scenario for DM response."""
        lower_input = user_input.lower()
        
        if "start" in lower_input or "begin" in lower_input:
            return "start_campaign"
        elif "dungeon" in lower_input or "explore" in lower_input:
            return "explore_dungeon"
        elif any(word in lower_input for word in ["attack", "fight", "combat"]):
            return "combat_start"
        
        return "default"
    
    def get_conversation_history(self) -> List[Dict]:
        """Get conversation history."""
        return self.conversation_history
    
    def get_agent_call_history(self) -> List[Dict]:
        """Get history of agent calls."""
        return self.agent_call_history
    
    def clear_history(self):
        """Clear all history."""
        self.conversation_history = []
        self.agent_call_history = []