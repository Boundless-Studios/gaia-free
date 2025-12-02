# Multi-Layer Narrative Architecture Proposal

## Executive Summary

This proposal addresses the fundamental tension between fast, focused agents that lack narrative depth and slow, intelligent models that provide rich storytelling but kill interactivity. We propose a multi-layer architecture that delivers immediate responses while progressively enhancing the narrative experience.

## Problem Statement

### Current Limitations

1. **Single Agent Routing Constraints**
   - Focused agents are fast but shallow
   - Missing holistic storytelling view
   - Limited discovery and environmental richness
   - User actions feel mechanical

2. **Model Performance Trade-offs**
   - Smart models (Kimi): Rich narratives but 3-5 second latency
   - Fast models (Qwen): Sub-second response but limited creativity
   - No middle ground currently exists

3. **Narrative Coherence Issues**
   - Single agents can't maintain story threads while handling immediate actions
   - Discovery feels random rather than narratively connected
   - Environmental details are often missing
   - Foreshadowing and tension building are lost

## Proposed Solution: Multi-Layer Narrative System

### Architecture Overview

```
USER INPUT
    ↓
[LAYER 1: Intent Analysis] - Fast (qwen) - 100ms
    ├→ Action parsing
    ├→ Emotional tone detection
    └→ Implicit desire extraction
    ↓
[LAYER 2: Parallel Execution] - Fast (multiple qwen agents) - 400ms
    ├→ Primary Agent (exploration/dialog/action)
    ├→ Environmental Scanner (always runs)
    ├→ Narrative Enrichment Agent (always runs)
    ├→ Discovery Generator (always runs)
    └→ Tension Tracker (always runs)
    ↓
[LAYER 3: Synthesis] - Smart but async (kimi) - 2-3s
    ├→ Weave responses together
    ├→ Add foreshadowing
    └→ Set up future hooks
    ↓
IMMEDIATE RESPONSE (Layers 1+2) - <500ms total
    +
ENRICHED RESPONSE (Layer 3) - Arrives 2-3s later
```

### Key Components

#### 1. Always-On Discovery Layer

Every user action triggers parallel discovery rolls:

```python
class DiscoveryLayer:
    """Runs on EVERY action to add interesting discoveries"""
    
    def generate(self, action: str, context: Dict) -> Dict:
        discoveries = {}
        
        # Environmental discoveries
        if self.roll_environmental(context):
            discoveries["background"] = self.generate_background_detail(context)
        
        # Character moments
        if self.roll_character_moment(context):
            discoveries["character"] = self.generate_character_detail(context)
        
        # Hidden opportunities
        if self.roll_opportunity(action, context):
            discoveries["opportunity"] = self.generate_opportunity(context)
        
        # Danger signs
        if self.roll_danger(context):
            discoveries["danger_hint"] = self.generate_danger_hint(context)
        
        return discoveries
```

#### 2. Narrative Enrichment Agent

Adds atmospheric depth to any action:

```python
class NarrativeEnricher:
    """Makes simple actions feel significant"""
    
    def enhance(self, action: str, result: Dict, context: Dict) -> Dict:
        return {
            "sensory_details": self.add_sensory_layer(action, context),
            "emotional_tone": self.detect_emotional_weight(action, result),
            "environmental_reaction": self.environment_responds(action, context),
            "narrative_connective": self.link_to_recent_events(action, context)
        }
```

#### 3. Progressive Response Delivery

```python
async def handle_user_action(user_input: str, context: Dict):
    # Phase 1: Immediate response (< 500ms)
    immediate_tasks = [
        route_to_primary_agent(user_input, context),
        discovery_layer.generate(user_input, context),
        environment_scanner.scan(context),
        narrative_enricher.quick_enhance(user_input, context)
    ]
    
    immediate_results = await asyncio.gather(*immediate_tasks)
    immediate_response = fast_synthesizer.merge(immediate_results)
    
    # Send immediately
    yield {
        "type": "immediate",
        "data": immediate_response,
        "timestamp": time.now()
    }
    
    # Phase 2: Narrative enhancement (2-3s later)
    enrichment = await smart_narrator.enrich(
        user_input,
        immediate_response,
        context,
        story_threads
    )
    
    yield {
        "type": "enrichment",
        "data": enrichment,
        "timestamp": time.now()
    }
```

### Implementation Phases

#### Phase 1: Parallel Discovery System (Week 1-2)
- Implement always-on discovery layer
- Add environmental scanner
- Create discovery probability engine
- Test with existing scene agents

#### Phase 2: Narrative Enrichment (Week 2-3)
- Build narrative enricher agent
- Implement sensory detail generation
- Add emotional tone detection
- Create narrative linking system

#### Phase 3: Progressive Delivery (Week 3-4)
- Implement async response system
- Update frontend to handle progressive updates
- Add smooth narrative blending
- Test latency and user experience

#### Phase 4: Smart Synthesis (Week 4-5)
- Integrate Kimi for narrative synthesis
- Implement foreshadowing system
- Add story thread weaving
- Create tension tracking

### Configuration Schema

```yaml
narrative_layers:
  immediate:
    agents:
      - primary_router
      - discovery_generator
      - environment_scanner
      - quick_enricher
    model: qwen3-32b
    max_latency_ms: 500
    parallel: true
    
  enrichment:
    agents:
      - narrative_synthesizer
      - foreshadow_generator
      - thread_weaver
    model: kimi-k2-instruct
    max_latency_ms: 3000
    optional: true
    async: true
    
  discovery_weights:
    environmental: 0.7
    character_moment: 0.5
    hidden_opportunity: 0.4
    danger_sign: 0.3
    story_callback: 0.6
```

### Frontend Integration

```javascript
// Handle progressive narrative updates
socket.on('narrative_response', (response) => {
  if (response.type === 'immediate') {
    // Display immediately
    showAction(response.data.action);
    showDiscovery(response.data.discovery);
    updateStatus(response.data.status);
  } else if (response.type === 'enrichment') {
    // Fade in narrative enhancement
    addNarrativeLayer(response.data.narrative);
    highlightForeshadowing(response.data.hints);
    updateMood(response.data.atmosphere);
  }
});
```

### Benefits

#### For Players
1. **Instant Feedback**: Actions resolve in <500ms
2. **Rich Discovery**: Something interesting on every turn
3. **Narrative Depth**: Story develops progressively
4. **Maintained Agency**: Never waiting for responses

#### For the System
1. **Scalable Complexity**: Simple actions stay simple
2. **Parallel Processing**: Utilize all available compute
3. **Graceful Degradation**: Works even if enrichment fails
4. **Learning Opportunity**: Track what resonates with players

#### For Narrative Quality
1. **Consistent Atmosphere**: Environmental details on every action
2. **Character Moments**: NPCs feel alive through small details
3. **Building Tension**: Foreshadowing happens naturally
4. **Connected Events**: Actions reference previous scenes

### Success Metrics

1. **Response Latency**
   - Immediate: < 500ms (P95)
   - Enrichment: < 3s (P95)

2. **Discovery Rate**
   - 60% of actions yield discoveries
   - 20% reveal story-relevant details

3. **Player Engagement**
   - Increased action frequency
   - Longer session duration
   - More exploratory behavior

4. **Narrative Coherence**
   - Story callbacks per session
   - Successful foreshadowing payoffs
   - Character consistency score

### Risk Mitigation

1. **Latency Spikes**: Enrichment layer is optional and async
2. **Inconsistency**: Fast synthesis layer ensures coherence
3. **Complexity**: Phased rollout allows testing
4. **Cost**: Smart model only used for enrichment, not critical path

### Alternative Approaches Considered

1. **Single Smart Model**: Too slow for interactivity
2. **Multiple Sequential Agents**: Adds latency
3. **Pre-generated Content**: Loses dynamic adaptation
4. **Client-side Enhancement**: Lacks context and coherence

### Conclusion

This multi-layer approach solves the speed vs. richness dilemma by delivering immediate responses while progressively enhancing the narrative. It maintains player agency while ensuring every action contributes to a rich, coherent story experience.

### Next Steps

1. Prototype the discovery layer with existing agents
2. Test latency with parallel agent execution
3. Design frontend progressive update system
4. Evaluate player response in controlled testing

---

*Document Version: 1.0*  
*Date: 2024-08-24*  
*Author: Gaia Development Team*