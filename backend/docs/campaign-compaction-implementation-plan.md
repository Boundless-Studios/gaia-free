# Campaign Compaction Implementation Plan

## Executive Summary

This document outlines a phased implementation plan for the campaign compaction strategy. The plan is designed to minimize risk, allow for incremental testing, and maintain backward compatibility throughout development.

## Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal**: Establish core infrastructure without breaking existing functionality

#### Tasks:
1. **Create CampaignStateManager** (2 days)
   - Implement thread-safe state management
   - Add transaction support
   - Create unit tests
   - File: `src/core/session/campaign_state_manager.py`

2. **Add Turn Tracking to Orchestrator** (1 day)
   - Add turn counter dictionary
   - Implement state persistence
   - Track turns per campaign
   - File: `src/core/agent_orchestration/orchestrator.py`

3. **Create Scene Detection Logic** (2 days)
   - Implement scene transition detection
   - Add scene ID generation
   - Track scene progression
   - File: `src/core/session/scene_tracker.py`

#### Deliverables:
- Working state manager with tests
- Turn tracking in orchestrator
- Scene detection algorithm
- No impact on existing campaigns

### Phase 2: Tool Enhancement (Week 2)
**Goal**: Upgrade formatter tools to support shared state

#### Tasks:
1. **Create Dual-Mode Tool Wrapper** (1 day)
   - Support both direct and shared state persistence
   - Maintain backward compatibility
   - File: `src/game/dnd_agents/tools/formatters/tool_wrapper.py`

2. **Enhance Existing Tools** (3 days)
   - Modify character_updater.py
   - Modify npc_updater.py
   - Modify environment_updater.py
   - Modify quest_updater.py
   - Add ID generation logic

3. **Create scene_narrative_updater Tool** (1 day)
   - Implement SceneInfo updates
   - Implement NarrativeInfo updates
   - Add to tool registry
   - File: `src/game/dnd_agents/tools/formatters/scene_narrative_updater.py`

#### Deliverables:
- Enhanced tools with shared state support
- New scene/narrative tool
- Comprehensive tool tests
- Tools remain backward compatible

### Phase 3: Persistence Agent (Week 3)
**Goal**: Implement the campaign persistence agent

#### Tasks:
1. **Create CampaignPersistenceAgent** (2 days)
   - Implement agent class
   - Add instructions and configuration
   - Register tools
   - File: `src/game/dnd_agents/campaign_persistence_agent.py`

2. **Implement Log Analysis** (2 days)
   - Parse conversation logs
   - Extract structured data
   - Identify update requirements
   - File: `src/game/dnd_agents/campaign_persistence_agent.py`

3. **Create Agent Tests** (1 day)
   - Unit tests for log analysis
   - Integration tests with tools
   - Performance benchmarks

#### Deliverables:
- Working persistence agent
- Log analysis functionality
- Agent test suite
- Agent can run standalone

### Phase 4: Orchestrator Integration (Week 4)
**Goal**: Wire compaction into the game flow

#### Tasks:
1. **Add Compaction Trigger** (1 day)
   - Implement 5-turn trigger
   - Add async compaction call
   - Handle failures gracefully
   - File: `src/core/agent_orchestration/orchestrator.py`

2. **Implement Log Management** (2 days)
   - Mark logs as compacted
   - Filter log loading
   - Add compaction metadata
   - File: `src/core/session/log_manager.py`

3. **Create Integration Tests** (2 days)
   - End-to-end campaign tests
   - Compaction trigger tests
   - Failure recovery tests

#### Deliverables:
- Compaction integrated into orchestrator
- Log filtering system
- Integration test suite
- System runs with compaction enabled

### Phase 5: Context Optimization (Week 5)
**Goal**: Use compacted data for better context

#### Tasks:
1. **Modify Campaign Loading** (2 days)
   - Load structured data first
   - Add recent logs only
   - Build hybrid context
   - File: `src/core/agent_orchestration/orchestrator.py`

2. **Optimize DM Context Builder** (2 days)
   - Use structured campaign data
   - Reduce token usage
   - Maintain quality
   - File: `src/engine/dm_context.py`

3. **Performance Testing** (1 day)
   - Benchmark with/without compaction
   - Measure response quality
   - Tune parameters

#### Deliverables:
- Optimized context loading
- Performance benchmarks
- Tuned system parameters
- Measurable improvements

## Implementation Details

### File Structure
```
src/
├── core/
│   ├── session/
│   │   ├── campaign_state_manager.py (NEW)
│   │   ├── scene_tracker.py (NEW)
│   │   └── log_manager.py (NEW)
│   └── agent_orchestration/
│       └── orchestrator.py (MODIFIED)
├── game/
│   └── dnd_agents/
│       ├── campaign_persistence_agent.py (NEW)
│       └── tools/
│           └── formatters/
│               ├── tool_wrapper.py (NEW)
│               ├── scene_narrative_updater.py (NEW)
│               └── *.py (MODIFIED)
└── engine/
    └── dm_context.py (MODIFIED)
```

### Testing Strategy

#### Unit Tests
- Each new component gets dedicated tests
- Mock external dependencies
- Test error conditions

#### Integration Tests
- Test complete workflows
- Verify data persistence
- Test failure recovery

#### Performance Tests
- Measure compaction time
- Track memory usage
- Monitor response quality

#### Regression Tests
- Ensure existing campaigns work
- Verify no data loss
- Test upgrade paths

### Rollout Strategy

#### Alpha Testing (Internal)
1. Enable for test campaigns only
2. Monitor performance and errors
3. Gather metrics

#### Beta Testing (Selected Users)
1. Enable for volunteer campaigns
2. Provide rollback option
3. Collect feedback

#### General Release
1. Enable by default for new campaigns
2. Provide migration for existing campaigns
3. Monitor system health

### Risk Mitigation

#### Risk: Data Loss
- **Mitigation**: Keep raw logs as backup
- **Mitigation**: Implement data validation
- **Mitigation**: Add rollback capability

#### Risk: Performance Degradation
- **Mitigation**: Run compaction async
- **Mitigation**: Add circuit breakers
- **Mitigation**: Monitor performance metrics

#### Risk: Breaking Changes
- **Mitigation**: Maintain backward compatibility
- **Mitigation**: Gradual rollout
- **Mitigation**: Feature flags

### Success Metrics

1. **Performance**
   - 50% reduction in context size for 20+ turn campaigns
   - <2 second compaction time for 5 turns
   - No increase in response latency

2. **Quality**
   - Reduced hallucination rate
   - Consistent character tracking
   - Maintained narrative continuity

3. **Reliability**
   - <0.1% compaction failure rate
   - Zero data loss incidents
   - Graceful degradation on errors

## Timeline Summary

- **Week 1**: Foundation - State management and tracking
- **Week 2**: Tools - Enhanced formatters with shared state
- **Week 3**: Agent - Persistence agent implementation
- **Week 4**: Integration - Wire into orchestrator
- **Week 5**: Optimization - Context improvements and tuning

Total Duration: 5 weeks

## Dependencies

1. **External Libraries**: None required
2. **Team Dependencies**: 
   - Core team for orchestrator changes
   - Agent team for new agent
   - QA team for testing

## Next Steps

1. Review and approve plan
2. Set up development branch
3. Begin Phase 1 implementation
4. Schedule weekly progress reviews

## Conclusion

This implementation plan provides a clear path to adding campaign compaction to Gaia. The phased approach minimizes risk while allowing for continuous testing and validation. With careful execution, we can significantly improve the system's ability to handle longer campaigns while maintaining quality and reliability.