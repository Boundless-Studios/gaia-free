# Prompt Template System Design

## Overview

This document describes the design for a template variable system for database-stored agent prompts. The system allows prompts to contain placeholder variables (like `{scene_description}`, `{turn_context}`) that are filled in at runtime with context-specific data.

## Current State

### Hardcoded Prompts
Currently, prompts are hardcoded in Python files with template variables using Python f-string syntax:

```python
ACTION_RESOLVER_BASE = """You are an action resolver for a roleplaying adventure game.

Scene: {scene_description}{turn_context}

CRITICAL RULES:
1. Resolve actions decisively
2. Be direct about success or failure
...
"""

def build_turn_context(current_turn: Dict[str, Any] | None) -> str:
    if not current_turn:
        return ""

    character_name = current_turn.get('character_name', 'Unknown')
    lines = [f"\n\nACTIVE PLAYER: {character_name}"]
    # ... build context string
    return "\n".join(lines)
```

### Problems with Current Approach
1. **No versioning** - Can't A/B test prompts or roll back changes
2. **Requires code deployment** - Changing prompts requires pushing new code
3. **No audit trail** - Can't see who changed what or when
4. **Hard to test** - Must test in development environment

## Proposed Solution

### Template Variable Syntax

Use `{{variable_name}}` syntax (double curly braces) to distinguish template variables from regular text:

**Advantages:**
- Clear visual distinction from regular text
- Common in templating systems (Jinja2, Handlebars, Mustache)
- Won't conflict with JSON in prompt examples
- Frontend can syntax-highlight these easily

**Example:**
```
You are an action resolver for a roleplaying adventure game.

Scene: {{scene_description}}{{turn_context}}

ACTIVE PLAYER: {{character_name}}
Player personality: {{personality_traits}}
```

### Variable Categories

#### 1. Context Variables
Provided at render time by the calling code:
- `{{scene_description}}` - Current scene narrative
- `{{turn_context}}` - Player turn information
- `{{character_name}}` - Active character
- `{{character_class}}` - Character class
- `{{personality_traits}}` - Character personality
- `{{player_action}}` - Action the player is attempting

#### 2. Conditional Sections (Future Enhancement)
For optional content that appears only if a variable exists:
```
{{#if character_class}}
Character class: {{character_class}}
{{/if}}
```

#### 3. Loops (Future Enhancement)
For lists of items:
```
{{#each party_members}}
- {{name}} ({{class}})
{{/each}}
```

## Architecture

### 1. Prompt Storage (Database)

```sql
-- prompts table (already exists)
CREATE TABLE prompt.prompts (
    prompt_id UUID PRIMARY KEY,
    agent_type VARCHAR(100),
    prompt_key VARCHAR(100),
    category VARCHAR(50),
    version_number INT,
    prompt_text TEXT,  -- Contains {{variable}} placeholders
    is_active BOOLEAN,
    ...
);
```

### 2. Prompt Service Layer

**File:** `backend/src/core/prompts/prompt_service.py`

```python
class PromptService:
    async def get_active_prompt(
        self,
        agent_type: str,
        prompt_key: str
    ) -> Prompt | None:
        """Get the active version of a prompt."""
        # Query database for active prompt
        # Return raw prompt with template variables

    async def render_prompt(
        self,
        agent_type: str,
        prompt_key: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Get active prompt and render with context variables.

        Args:
            agent_type: Type of agent (e.g., 'action_resolver')
            prompt_key: Specific prompt (e.g., 'base_prompt')
            context: Dictionary of variables to substitute

        Returns:
            Rendered prompt text with variables filled in

        Raises:
            PromptNotFoundError: If no active prompt exists
            TemplateMissingVariableError: If required variable not in context
        """
        prompt = await self.get_active_prompt(agent_type, prompt_key)
        if not prompt:
            # Fall back to hardcoded prompt
            return self._fallback_to_hardcoded(agent_type, prompt_key, context)

        return self._render_template(prompt.prompt_text, context)
```

### 3. Template Renderer

**File:** `backend/src/core/prompts/template_renderer.py`

```python
import re
from typing import Dict, Any, Set

class TemplateRenderer:
    """Renders prompt templates with variable substitution."""

    # Regex to match {{variable_name}}
    VARIABLE_PATTERN = re.compile(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}')

    def render(
        self,
        template: str,
        context: Dict[str, Any],
        strict: bool = False
    ) -> str:
        """
        Render a template string with context variables.

        Args:
            template: Template string with {{variable}} placeholders
            context: Dictionary of variable values
            strict: If True, raise error on missing variables
                   If False, leave missing variables as empty string

        Returns:
            Rendered string

        Raises:
            TemplateMissingVariableError: If strict=True and variable missing
        """
        missing_vars = self.get_missing_variables(template, context)

        if missing_vars and strict:
            raise TemplateMissingVariableError(
                f"Missing required variables: {', '.join(missing_vars)}"
            )

        def replace_var(match):
            var_name = match.group(1)
            value = context.get(var_name, '')

            # Convert non-string values to strings
            if value is None:
                return ''
            return str(value)

        return self.VARIABLE_PATTERN.sub(replace_var, template)

    def get_required_variables(self, template: str) -> Set[str]:
        """Extract all variable names from a template."""
        return set(self.VARIABLE_PATTERN.findall(template))

    def get_missing_variables(
        self,
        template: str,
        context: Dict[str, Any]
    ) -> Set[str]:
        """Find variables in template that are not in context."""
        required = self.get_required_variables(template)
        provided = set(context.keys())
        return required - provided

    def validate_template(self, template: str) -> tuple[bool, list[str]]:
        """
        Validate template syntax.

        Returns:
            (is_valid, error_messages)
        """
        errors = []

        # Check for unmatched braces
        open_count = template.count('{{')
        close_count = template.count('}}')
        if open_count != close_count:
            errors.append(f"Unmatched braces: {open_count} opening, {close_count} closing")

        # Check for invalid variable names
        for match in self.VARIABLE_PATTERN.finditer(template):
            var_name = match.group(1)
            if not var_name.replace('_', '').isalnum():
                errors.append(f"Invalid variable name: {var_name}")

        return (len(errors) == 0, errors)
```

### 4. Agent Integration

**Example:** Action Resolver Agent

```python
from src.core.prompts import PromptService
from src.core.prompts.template_renderer import TemplateRenderer

class ActionResolverAgent:
    def __init__(self):
        self.prompt_service = PromptService()
        self.renderer = TemplateRenderer()

    async def resolve_action(
        self,
        player_action: str,
        scene: Scene,
        current_turn: PlayerTurn
    ):
        """Resolve a player action."""

        # Build context for prompt template
        context = {
            'scene_description': scene.description,
            'turn_context': self._build_turn_context(current_turn),
            'character_name': current_turn.character_name,
            'character_class': current_turn.character_class,
            'personality_traits': ', '.join(current_turn.personality_traits),
            'player_action': player_action,
        }

        # Get rendered prompt from database
        try:
            prompt_text = await self.prompt_service.render_prompt(
                agent_type='action_resolver',
                prompt_key='base_prompt',
                context=context
            )
        except PromptNotFoundError:
            # Fallback to hardcoded prompt
            prompt_text = ACTION_RESOLVER_BASE.format(**context)

        # Run agent with rendered prompt
        response = await self.run_agent(prompt_text, player_action)
        return response
```

## Migration Strategy

### Phase 1: Add Template Rendering Support (Current)
1. ✅ Create database schema for prompts
2. ✅ Create admin UI for prompt management
3. ✅ Create API endpoints for CRUD operations
4. 🔄 Implement TemplateRenderer class
5. 🔄 Integrate PromptService with agents

### Phase 2: Migrate Prompts to Database
1. Create migration script to populate initial prompts
2. For each agent type:
   - Extract hardcoded prompts
   - Convert f-string syntax to {{variable}} syntax
   - Insert into database as version 1
   - Mark as active
3. Update agent code to use PromptService
4. Test thoroughly with existing functionality

### Phase 3: Deprecate Hardcoded Prompts
1. Add deprecation warnings to hardcoded prompt files
2. Keep hardcoded prompts as fallback for safety
3. Monitor for any fallback usage in logs
4. After stable period, remove hardcoded prompts

## Frontend Template Editor

### Variable Highlighting
The PromptManager UI already highlights `{{variable}}` syntax:

```jsx
const renderPromptWithHighlights = (text) => {
  const parts = text.split(/(\{\{[^}]+\}\})/g);

  return parts.map((part, idx) => {
    if (part.match(/^\{\{[^}]+\}\}$/)) {
      return (
        <span key={idx} className="bg-yellow-100 text-yellow-900 px-1 rounded font-semibold">
          {part}
        </span>
      );
    }
    return <span key={idx}>{part}</span>;
  });
};
```

### Variable Documentation Panel (Future Enhancement)
Add a sidebar showing:
- Available variables for each agent type
- Example values
- Whether variable is required or optional

## Testing Strategy

### Unit Tests
```python
# test_template_renderer.py

def test_render_simple_variable():
    renderer = TemplateRenderer()
    template = "Hello {{name}}!"
    context = {'name': 'World'}
    assert renderer.render(template, context) == "Hello World!"

def test_render_missing_variable_strict():
    renderer = TemplateRenderer()
    template = "Hello {{name}}!"
    context = {}
    with pytest.raises(TemplateMissingVariableError):
        renderer.render(template, context, strict=True)

def test_render_missing_variable_lenient():
    renderer = TemplateRenderer()
    template = "Hello {{name}}!"
    context = {}
    assert renderer.render(template, context, strict=False) == "Hello !"

def test_get_required_variables():
    renderer = TemplateRenderer()
    template = "Scene: {{scene_description}}{{turn_context}}"
    vars = renderer.get_required_variables(template)
    assert vars == {'scene_description', 'turn_context'}
```

### Integration Tests
```python
# test_prompt_service.py

async def test_render_prompt_from_database(db_session):
    service = PromptService(db_session)

    # Create test prompt
    await create_test_prompt(
        agent_type='action_resolver',
        prompt_key='base_prompt',
        prompt_text='Scene: {{scene_description}}'
    )

    # Render with context
    result = await service.render_prompt(
        'action_resolver',
        'base_prompt',
        {'scene_description': 'A dark cave'}
    )

    assert result == 'Scene: A dark cave'
```

## Security Considerations

### 1. Template Injection
- **Risk:** Malicious admin could inject code via template variables
- **Mitigation:**
  - Admin access restricted to super-admins only
  - No code execution in templates (just string substitution)
  - Validate template syntax before saving

### 2. Variable Validation
- **Risk:** Invalid variable names could break rendering
- **Mitigation:**
  - Validate variable names match pattern `[a-zA-Z_][a-zA-Z0-9_]*`
  - Show validation errors in UI before saving

### 3. Missing Variables
- **Risk:** Missing required variables could produce broken prompts
- **Mitigation:**
  - Document required variables for each agent type
  - Log warnings when variables are missing
  - Use lenient mode (empty string) as default

## Performance Considerations

### Caching Strategy
```python
class PromptService:
    def __init__(self):
        self._cache = {}  # In-memory cache
        self._cache_ttl = 300  # 5 minutes

    async def get_active_prompt(self, agent_type: str, prompt_key: str):
        cache_key = f"{agent_type}:{prompt_key}"

        # Check cache
        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached

        # Fetch from database
        prompt = await self._fetch_from_db(agent_type, prompt_key)

        # Update cache
        self._cache[cache_key] = (prompt, time.time())

        return prompt

    async def invalidate_cache(self, agent_type: str):
        """Called when a prompt is activated/deactivated."""
        # Clear cache entries for this agent type
        keys_to_remove = [k for k in self._cache if k.startswith(f"{agent_type}:")]
        for key in keys_to_remove:
            del self._cache[key]
```

## Future Enhancements

### 1. Conditional Sections
```
{{#if character_class}}
Your class: {{character_class}}
{{/if}}
```

### 2. Loops
```
{{#each inventory_items}}
- {{name}} ({{quantity}})
{{/each}}
```

### 3. Helper Functions
```
{{uppercase character_name}}
{{truncate description 100}}
{{join personality_traits ", "}}
```

### 4. Template Inheritance
```
{{extends "base_dm_prompt"}}
{{block rules}}
Custom rules here
{{/block}}
```

### 5. Variable Type Hints
Add metadata to prompts documenting expected variable types:
```json
{
  "variables": {
    "scene_description": {
      "type": "string",
      "required": true,
      "description": "Current scene narrative"
    },
    "character_name": {
      "type": "string",
      "required": true,
      "description": "Active player's character name"
    }
  }
}
```

## Open Questions

1. **Should we support nested variables?**
   - Example: `{{player.name}}` vs `{{player_name}}`
   - Decision: Start with flat variables, add nesting if needed

2. **How to handle lists/arrays?**
   - Example: `{{personality_traits}}` where value is `['brave', 'curious']`
   - Decision: Convert to comma-separated string for now, add loop support later

3. **Error handling for production?**
   - Should missing variables crash or degrade gracefully?
   - Decision: Degrade gracefully (empty string), log warning

4. **Version control for templates?**
   - Already handled by prompt versioning system
   - Each prompt change creates new version

## References

- Frontend PR: Prompt Manager UI with template highlighting
- Database Schema: `backend/db/src/schema.sql` - prompts table
- API Endpoints: `backend/src/api/prompts_endpoints.py`
- Existing hardcoded prompts: `backend/src/game/scene_agents/prompts/`
