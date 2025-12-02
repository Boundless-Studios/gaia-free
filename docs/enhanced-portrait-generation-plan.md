# Enhanced Character Portrait Generation Plan

## Objective
Build a feature that ensures the image_generator agent incorporates ALL character descriptive fields into portrait generation while maintaining agent creativity and variety, ensuring critical character information is always preserved in the finalized prompt.

## Current State Analysis

### Existing Flow
1. **Character Creation**: CharacterInfo model contains visual fields (gender, age_category, build, height_description, facial_expression, facial_features, attire, primary_weapon, distinguishing_feature, background_setting, pose)
2. **Portrait Generation**: CharacterPortraitGenerator builds a basic prompt from available fields
3. **Agent Enhancement**: ImageGeneratorAgent.enhance_prompt() refines the prompt using AI
4. **Image Creation**: Final enhanced prompt sent to image generation service

### Current Limitations
- Not all character fields are consistently used in prompt building
- Agent enhancement sometimes drops critical character information
- No validation that essential character attributes are preserved
- Limited structured guidance for the enhancement agent

## Proposed Enhancement Architecture

### 1. Core Prompt Composition System

#### A. Mandatory Field Preservation
Create a two-tier prompt system:
- **Critical Fields** (MUST be preserved): name, gender, race, class, age_category
- **Enhanced Fields** (SHOULD be included): all other visual descriptors

#### B. Structured Prompt Builder
```python
class EnhancedPortraitPromptBuilder:
    """Builds comprehensive prompts ensuring all character data is included."""

    CRITICAL_TEMPLATE = "{name}, {gender} {race} {class}"

    FIELD_CATEGORIES = {
        'identity': ['name', 'gender', 'race', 'class'],
        'physical': ['age_category', 'build', 'height_description'],
        'facial': ['facial_expression', 'facial_features'],
        'equipment': ['attire', 'primary_weapon'],
        'unique': ['distinguishing_feature'],
        'environment': ['background_setting', 'pose']
    }

    def build_structured_prompt(self, character_info: CharacterInfo) -> Dict[str, str]:
        """Build categorized prompt components."""
        return {
            'critical': self._build_critical_section(character_info),
            'physical': self._build_physical_section(character_info),
            'facial': self._build_facial_section(character_info),
            'equipment': self._build_equipment_section(character_info),
            'unique': self._build_unique_section(character_info),
            'environment': self._build_environment_section(character_info)
        }
```

### 2. Enhanced Agent Prompt Engineering

#### A. Modified enhance_prompt() Method
Update the ImageGeneratorAgent.enhance_prompt() to use structured guidance:

```python
async def enhance_prompt_v2(self, structured_prompt: Dict[str, str], image_type: str = "portrait") -> str:
    """Enhanced version that preserves critical information while adding creative details."""

    enhancement_request = f"""
    You are enhancing a character portrait prompt. You MUST include ALL of the following information:

    CRITICAL (MUST PRESERVE EXACTLY):
    {structured_prompt['critical']}

    REQUIRED ELEMENTS (MUST INCLUDE):
    - Physical: {structured_prompt['physical']}
    - Facial: {structured_prompt['facial']}
    - Equipment: {structured_prompt['equipment']}
    - Unique: {structured_prompt['unique']}
    - Environment: {structured_prompt['environment']}

    ENHANCEMENT GUIDELINES:
    1. Add creative details that complement but don't contradict the provided information
    2. Enhance atmosphere and mood while preserving character identity
    3. Add artistic details (lighting, perspective, composition)
    4. Ensure all critical and required elements appear in your output
    5. Keep under 400 characters total

    Return ONLY the enhanced prompt. Include ALL provided information plus your creative additions.
    """
```

#### B. Prompt Validation
Add validation to ensure critical fields are present in the enhanced prompt:

```python
def validate_enhanced_prompt(self, original_fields: Dict, enhanced_prompt: str) -> bool:
    """Validate that critical character information is preserved."""
    critical_fields = ['name', 'gender', 'race', 'class']

    for field in critical_fields:
        if field in original_fields and original_fields[field]:
            # Check if the value appears in the enhanced prompt
            if str(original_fields[field]).lower() not in enhanced_prompt.lower():
                logger.warning(f"Critical field '{field}' missing from enhanced prompt")
                return False

    return True
```

### 3. Character Field Extraction Enhancement

#### A. Automatic Field Population
When creating characters, automatically extract visual descriptors from the description:

```python
class CharacterVisualExtractor:
    """Extracts visual metadata from character descriptions."""

    GENDER_PATTERNS = {
        'male': ['he', 'his', 'man', 'boy', 'male'],
        'female': ['she', 'her', 'woman', 'girl', 'female']
    }

    AGE_PATTERNS = {
        'young': ['young', 'youth', 'teenage', 'adolescent'],
        'adult': ['adult', 'middle-aged'],
        'elderly': ['old', 'elderly', 'aged', 'ancient']
    }

    BUILD_PATTERNS = {
        'slender': ['slender', 'thin', 'lithe', 'lean'],
        'athletic': ['athletic', 'fit', 'muscular', 'strong'],
        'stocky': ['stocky', 'broad', 'stout', 'thick']
    }

    def extract_visual_fields(self, description: str, backstory: str = "") -> Dict[str, str]:
        """Extract visual metadata from text descriptions."""
        fields = {}

        combined_text = f"{description} {backstory}".lower()

        # Extract gender
        for gender, patterns in self.GENDER_PATTERNS.items():
            if any(pattern in combined_text for pattern in patterns):
                fields['gender'] = gender
                break

        # Extract age category
        for age, patterns in self.AGE_PATTERNS.items():
            if any(pattern in combined_text for pattern in patterns):
                fields['age_category'] = age
                break

        # Extract build
        for build, patterns in self.BUILD_PATTERNS.items():
            if any(pattern in combined_text for pattern in patterns):
                fields['build'] = build
                break

        # Extract other fields using NLP or regex patterns
        fields.update(self._extract_equipment(combined_text))
        fields.update(self._extract_facial_features(combined_text))

        return fields
```

### 4. Implementation Flow

#### Phase 1: Core Infrastructure
1. Create `EnhancedPortraitPromptBuilder` class in `src/core/character/portrait_prompt_builder.py`
2. Implement structured prompt building with field categorization
3. Add prompt validation logic

#### Phase 2: Agent Enhancement
1. Update `ImageGeneratorAgent.enhance_prompt()` to accept structured prompts
2. Modify prompt enhancement instructions for better field preservation
3. Add validation after enhancement to ensure critical fields remain

#### Phase 3: Field Extraction
1. Create `CharacterVisualExtractor` class
2. Integrate with character creation flow
3. Auto-populate visual fields when missing

#### Phase 4: Integration
1. Update `CharacterPortraitGenerator` to use new prompt builder
2. Modify the image generation flow to validate enhanced prompts
3. Add retry logic if validation fails

## Testing Strategy

### 1. Backend-Only Test Harness

Create a standalone test script that doesn't require frontend interaction:

```python
# scripts/claude_helpers/test_enhanced_portrait_generation.py

import asyncio
from src.core.character.models.character_info import CharacterInfo
from src.core.character.portrait_prompt_builder import EnhancedPortraitPromptBuilder
from src.game.dnd_agents.image_generator import ImageGeneratorAgent

async def test_portrait_generation():
    """Test portrait generation with various character configurations."""

    # Test Case 1: Fully populated character
    character_full = CharacterInfo(
        character_id="test_001",
        name="Thorin Ironforge",
        character_class="Fighter",
        race="Dwarf",
        gender="male",
        age_category="middle-aged",
        build="stocky",
        height_description="short and stout",
        facial_expression="determined",
        facial_features="thick braided beard, scarred cheek",
        attire="plate armor with clan symbols",
        primary_weapon="massive warhammer",
        distinguishing_feature="glowing rune on forehead",
        background_setting="mountain fortress",
        pose="standing proudly"
    )

    # Test Case 2: Minimal character (tests field extraction)
    character_minimal = CharacterInfo(
        character_id="test_002",
        name="Lyra Moonwhisper",
        character_class="Wizard",
        race="Elf",
        description="A young elven woman with flowing silver hair"
    )

    # Test Case 3: Partial character (tests enhancement)
    character_partial = CharacterInfo(
        character_id="test_003",
        name="Gareth the Bold",
        character_class="Paladin",
        race="Human",
        gender="male",
        facial_expression="confident",
        attire="shining armor"
    )

    # Run tests
    for character in [character_full, character_minimal, character_partial]:
        print(f"\n=== Testing {character.name} ===")

        # Build structured prompt
        builder = EnhancedPortraitPromptBuilder()
        structured = builder.build_structured_prompt(character)
        print(f"Structured Prompt: {structured}")

        # Enhance prompt
        agent = ImageGeneratorAgent()
        enhanced = await agent.enhance_prompt_v2(structured, "portrait")
        print(f"Enhanced Prompt: {enhanced}")

        # Validate
        is_valid = builder.validate_enhanced_prompt(character.to_dict(), enhanced)
        print(f"Validation: {'PASSED' if is_valid else 'FAILED'}")

        # Generate image (mock or real)
        if is_valid:
            result = await agent.generate_image_tool(
                prompt=enhanced,
                image_type="portrait",
                style="fantasy art"
            )
            print(f"Generation Result: {result.get('success')}")

if __name__ == "__main__":
    asyncio.run(test_portrait_generation())
```

### 2. Unit Tests

```python
# backend/test/core/character/test_portrait_prompt_builder.py

def test_critical_fields_preserved():
    """Test that critical fields are always included."""
    builder = EnhancedPortraitPromptBuilder()
    character = CharacterInfo(
        character_id="test",
        name="Test Character",
        character_class="Fighter",
        race="Human",
        gender="female"
    )

    structured = builder.build_structured_prompt(character)
    assert "Test Character" in structured['critical']
    assert "female" in structured['critical']
    assert "Human" in structured['critical']
    assert "Fighter" in structured['critical']

def test_field_extraction():
    """Test automatic field extraction from descriptions."""
    extractor = CharacterVisualExtractor()

    description = "A young elven woman with silver hair and green eyes"
    fields = extractor.extract_visual_fields(description)

    assert fields.get('gender') == 'female'
    assert fields.get('age_category') == 'young'
    assert 'silver hair' in fields.get('facial_features', '')

def test_prompt_validation():
    """Test that validation catches missing critical fields."""
    builder = EnhancedPortraitPromptBuilder()

    original = {
        'name': 'Aragorn',
        'race': 'Human',
        'class': 'Ranger',
        'gender': 'male'
    }

    # Valid prompt
    valid_prompt = "Aragorn, male Human Ranger with weathered features"
    assert builder.validate_enhanced_prompt(original, valid_prompt) == True

    # Invalid prompt (missing gender)
    invalid_prompt = "Aragorn, Human Ranger with weathered features"
    assert builder.validate_enhanced_prompt(original, invalid_prompt) == False
```

### 3. Integration Tests

```python
# backend/test/integration/test_portrait_generation_flow.py

async def test_complete_portrait_flow():
    """Test the entire portrait generation flow."""

    # Create character with partial information
    character = CharacterInfo(
        character_id="integration_test",
        name="Elena Starweaver",
        character_class="Sorcerer",
        race="Half-Elf",
        description="A mysterious sorceress with arcane tattoos"
    )

    # Extract visual fields
    extractor = CharacterVisualExtractor()
    extracted = extractor.extract_visual_fields(character.description)

    # Update character with extracted fields
    for field, value in extracted.items():
        setattr(character, field, value)

    # Generate portrait
    generator = CharacterPortraitGenerator()
    result = await generator.generate_portrait(character)

    # Validate result
    assert result['success'] == True
    assert 'Elena Starweaver' in result.get('prompt', '')
    assert 'Half-Elf' in result.get('prompt', '')
    assert 'Sorcerer' in result.get('prompt', '')
```

## Behavioral Testing

### Test Scenarios

1. **Variety Test**: Generate 5 portraits for the same character, verify:
   - All contain critical information
   - Each has unique creative additions
   - Visual consistency maintained

2. **Field Coverage Test**: Create characters with different combinations of fields:
   - Full fields populated
   - Only critical fields
   - Mixed partial fields

3. **Enhancement Quality Test**: Verify agent additions:
   - Atmospheric details added
   - Artistic elements included
   - No contradictions with source data

4. **Failure Recovery Test**: Test system behavior when:
   - Image service unavailable
   - Enhancement fails validation
   - Partial field extraction

### Monitoring & Validation

```python
class PortraitGenerationMonitor:
    """Monitor portrait generation quality and consistency."""

    def __init__(self):
        self.generation_log = []

    def log_generation(self, character_info: CharacterInfo,
                      structured_prompt: Dict,
                      enhanced_prompt: str,
                      result: Dict):
        """Log each generation for analysis."""
        self.generation_log.append({
            'timestamp': datetime.now(),
            'character_name': character_info.name,
            'fields_provided': sum(1 for f in character_info.__dict__.values() if f),
            'critical_preserved': self._check_critical_preservation(character_info, enhanced_prompt),
            'enhancement_length': len(enhanced_prompt),
            'success': result.get('success'),
            'service_used': result.get('service')
        })

    def generate_report(self):
        """Generate quality report."""
        total = len(self.generation_log)
        successful = sum(1 for log in self.generation_log if log['success'])
        critical_preserved = sum(1 for log in self.generation_log if log['critical_preserved'])

        print(f"Portrait Generation Report")
        print(f"Total Generations: {total}")
        print(f"Success Rate: {successful/total*100:.1f}%")
        print(f"Critical Field Preservation: {critical_preserved/total*100:.1f}%")
```

## Success Metrics

1. **Critical Field Preservation**: 100% of generations include all critical fields
2. **Enhanced Field Inclusion**: >80% of provided fields appear in final prompt
3. **Creative Enhancement**: Each prompt includes 3+ agent-added details
4. **Generation Success**: >95% successful image generation
5. **Prompt Length**: Final prompts between 200-400 characters
6. **Variety**: <20% similarity between prompts for same character

## Timeline

- **Week 1**: Implement core prompt builder and validation
- **Week 2**: Update agent enhancement logic and integration
- **Week 3**: Create field extractor and auto-population
- **Week 4**: Testing, monitoring, and refinement

## Risk Mitigation

1. **Performance**: Cache enhanced prompts for repeated generations
2. **Consistency**: Store prompt templates for character types
3. **Fallback**: If enhancement fails, use structured prompt directly
4. **Validation**: Multiple validation checkpoints in the flow