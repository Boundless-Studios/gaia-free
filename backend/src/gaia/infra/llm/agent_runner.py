"""
Generic agent runner that handles agent execution with proper model configuration.
"""
import logging
from typing import Any, Optional, Dict, TypeVar
from agents import Agent, ModelSettings, Runner, RunConfig
from pydantic import ValidationError
from pydantic.type_adapter import TypeAdapter
from gaia.infra.llm.model_manager import create_model_provider_for_model
from gaia.utils.json_sanitizer import sanitize_json_string

logger = logging.getLogger(__name__)

# Type variable for generic validation
T = TypeVar('T')


class AgentRunner:
    """Generic runner for executing agents with proper model configuration."""

    @staticmethod
    def _patch_json_validation():
        """Patch the agents library JSON validation to include sanitization.

        This monkey-patches the agents.util._json.validate_json function to
        automatically sanitize malformed JSON before validation.
        """
        try:
            import agents.util._json as agents_json

            # Store original function if not already patched
            if not hasattr(agents_json, '_original_validate_json'):
                agents_json._original_validate_json = agents_json.validate_json

                def patched_validate_json(json_str: str, type_adapter: TypeAdapter, partial: bool):
                    """Patched JSON validation with sanitization."""
                    try:
                        # Try original validation first
                        return agents_json._original_validate_json(json_str, type_adapter, partial)
                    except Exception as e:
                        # If validation fails, try with sanitized JSON
                        if "Invalid JSON" in str(e) or "control character" in str(e):
                            logger.debug(f"JSON validation failed, attempting sanitization: {str(e)[:200]}")
                            try:
                                sanitized_json = sanitize_json_string(json_str)
                                logger.debug("JSON sanitized successfully, retrying validation")
                                return agents_json._original_validate_json(sanitized_json, type_adapter, partial)
                            except Exception as e2:
                                logger.warning(f"JSON validation still failed after sanitization: {str(e2)[:200]}")
                                # Fall back to original exception
                                raise e
                        else:
                            # Not a JSON format issue, raise original
                            raise

                # Apply the patch
                agents_json.validate_json = patched_validate_json
                logger.debug("Patched agents library JSON validation with sanitization")

        except ImportError:
            logger.warning("Could not import agents.util._json for patching")
        except Exception as e:
            logger.warning(f"Failed to patch JSON validation: {e}")

    @staticmethod
    async def run(
        agent: Agent,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tool_choice: Optional[str] = "auto",
        parallel_tool_calls: bool = False,
        max_turns: Optional[int] = None,
        context: Optional[Any] = None,
        **kwargs
    ) -> Any:
        """Run an agent using the Runner pattern with proper model configuration.

        Args:
            agent: The agent to run
            prompt: The prompt to send to the agent
            model: Optional model override (defaults to agent's model if available)
            temperature: Temperature for generation (default 0.7)
            tool_choice: Tool choice behavior (default "auto", can be "required", "none")
            parallel_tool_calls: Whether to allow parallel tool calls
            max_turns: Maximum number of turns for the agent (default None uses Runner's default)
            context: Optional context object to pass to tools and hooks
            **kwargs: Additional keyword arguments for ModelSettings

        Returns:
            The result from the agent run
        """
        # Apply JSON sanitization patch to agents library
        AgentRunner._patch_json_validation()

        runner = Runner()
        
        # Use provided model or try to get from agent
        model_key = model or getattr(agent, 'model', None)
        if not model_key:
            raise ValueError("No model specified and agent has no default model")
        
        # Get model configuration
        model_provider, resolved_model = create_model_provider_for_model(model_key)
        
        # Build model settings - separate out non-ModelSettings kwargs
        model_settings_kwargs = {
            "temperature": temperature,
        }

        # Only add tool_choice and parallel_tool_calls if agent has tools
        # get_all_tools requires a run_context, so we'll check for tools attribute instead
        if hasattr(agent, 'tools') and agent.tools:
            model_settings_kwargs["tool_choice"] = tool_choice
            model_settings_kwargs["parallel_tool_calls"] = parallel_tool_calls
        
        # Add any additional kwargs that are valid for ModelSettings
        for key, value in kwargs.items():
            if key not in ['max_turns']:  # Filter out Runner-specific args
                model_settings_kwargs[key] = value
        
        # Create run config
        run_config = RunConfig(
            model=resolved_model,
            model_provider=model_provider,
            model_settings=ModelSettings(**model_settings_kwargs)
        )
        
        # Run the agent
        try:
            logger.debug(f"Running agent {agent.name if hasattr(agent, 'name') else 'Unknown'} with model {resolved_model}")
            if max_turns:
                logger.debug(f"  Max turns: {max_turns}")
            
            # Runner.run expects positional args: agent, prompt, then keyword args
            run_kwargs = {"run_config": run_config}

            # Only add optional parameters if they're provided
            if max_turns is not None:
                run_kwargs["max_turns"] = max_turns
            if context is not None:
                run_kwargs["context"] = context

            result = await runner.run(
                agent,
                prompt,
                **run_kwargs
            )
            return result
        except Exception as e:
            # Prepare error context - be careful not to hide the actual error
            try:
                agent_name = getattr(agent, 'name', 'Unknown agent')
            except Exception:
                agent_name = 'Unknown agent (error getting name)'

            error_type = type(e).__name__
            error_details = {
                'agent': agent_name,
                'model': resolved_model,
                'error_type': error_type,
                'error_message': str(e),
                'has_partial_result': 'result' in locals()
            }

            # Special handling for OutputGuardrail exceptions
            if "OutputGuardrail" in error_type or "OutputGuardrail" in str(e):
                logger.error(
                    "OutputGuardrail validation failed - Agent: '%(agent)s', Model: '%(model)s', Error: %(error_message)s",
                    error_details
                )
                logger.error(
                    "This typically means the agent's output didn't match the expected format or contained disallowed content"
                )

                # Collect and log guardrail context if available
                context = AgentRunner._collect_guardrail_context(e)
                if context:
                    error_details['guardrail_context'] = context
                    logger.error("Guardrail exception context: %s", context)

                # Log prompt preview for debugging
                prompt_preview = AgentRunner._safe_preview(prompt)
                if prompt_preview:
                    error_details['prompt_preview'] = prompt_preview
                    logger.debug("Prompt excerpt when guardrail triggered: %s", prompt_preview)

                # Log the partial result if available for debugging
                if error_details['has_partial_result']:
                    partial_result = AgentRunner._safe_preview(result)
                    error_details['partial_result'] = partial_result
                    logger.debug("Partial result before guardrail: %s", partial_result)

                # Create enhanced exception with all context
                enhanced_error = RuntimeError(
                    f"Agent execution failed with {error_type}: {error_details}"
                )
                enhanced_error.__cause__ = e
                enhanced_error.error_details = error_details
                raise enhanced_error from e
            else:
                # General error handling with structured context
                logger.error(
                    "Agent execution error - Agent: '%(agent)s', Model: '%(model)s', Type: %(error_type)s, Message: %(error_message)s",
                    error_details,
                    exc_info=True
                )

                # Add any partial results to error details
                if error_details['has_partial_result']:
                    error_details['partial_result'] = AgentRunner._safe_preview(result)

                # Re-raise with enhanced context
                enhanced_error = RuntimeError(
                    f"Agent execution failed: {error_details}"
                )
                enhanced_error.__cause__ = e
                enhanced_error.error_details = error_details
                raise enhanced_error from e

    @staticmethod
    def run_streamed(
        agent: Agent,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        tool_choice: Optional[str] = "auto",
        parallel_tool_calls: bool = False,
        max_turns: Optional[int] = None,
        context: Optional[Any] = None,
        **kwargs,
    ):
        """Run an agent using Runner.run_streamed for incremental consumption."""
        AgentRunner._patch_json_validation()

        runner = Runner()

        model_key = model or getattr(agent, 'model', None)
        if not model_key:
            raise ValueError("No model specified and agent has no default model")

        model_provider, resolved_model = create_model_provider_for_model(model_key)

        model_settings_kwargs = {
            "temperature": temperature,
        }

        # Only add tool_choice and parallel_tool_calls if agent has tools
        if hasattr(agent, 'tools') and agent.tools:
            model_settings_kwargs["tool_choice"] = tool_choice
            model_settings_kwargs["parallel_tool_calls"] = parallel_tool_calls

        for key, value in kwargs.items():
            if key not in ['max_turns']:
                model_settings_kwargs[key] = value

        run_config = RunConfig(
            model=resolved_model,
            model_provider=model_provider,
            model_settings=ModelSettings(**model_settings_kwargs),
        )

        run_kwargs = {"run_config": run_config}
        if max_turns is not None:
            run_kwargs["max_turns"] = max_turns
        if context is not None:
            run_kwargs["context"] = context

        return runner.run_streamed(
            agent,
            prompt,
            **run_kwargs,
        )

    @staticmethod
    def _coerce_item_to_text(item: Any) -> Optional[str]:
        """Attempt to extract human-readable text from varied agent output structures."""
        if item is None:
            return None

        if isinstance(item, str):
            return item

        # Handle lists at top level by recursively processing items
        if isinstance(item, list):
            pieces = [
                piece
                for piece in (AgentRunner._coerce_item_to_text(part) for part in item)
                if piece
            ]
            if pieces:
                return "".join(pieces)

        # Attempt to use agents.ItemHelpers when available
        try:
            from agents.items import ItemHelpers, MessageOutputItem  # type: ignore
        except Exception:  # noqa: BLE001
            ItemHelpers = None  # type: ignore[assignment]
            MessageOutputItem = None  # type: ignore[assignment]

        if MessageOutputItem is not None and isinstance(item, MessageOutputItem):  # type: ignore[arg-type]
            try:
                text = ItemHelpers.text_message_output(item)  # type: ignore[union-attr]
                if text:
                    return text
            except Exception:  # noqa: BLE001
                pass

        raw_item = getattr(item, "raw_item", None)
        if raw_item is not None and raw_item is not item:
            extracted = AgentRunner._coerce_item_to_text(raw_item)
            if extracted:
                return extracted

        if hasattr(item, "model_dump"):
            try:
                dumped = item.model_dump(exclude_unset=True)
                extracted = AgentRunner._coerce_item_to_text(dumped)
                if extracted:
                    return extracted
            except Exception:  # noqa: BLE001
                pass

        if isinstance(item, dict):
            for key in ("text", "content", "output"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            # Recursively inspect nested content structures
            for value in item.values():
                extracted = AgentRunner._coerce_item_to_text(value)
                if extracted:
                    return extracted

        content = getattr(item, "content", None)
        if isinstance(content, str):
            if content.strip():
                return content
        elif isinstance(content, list):
            pieces = [
                piece
                for piece in (AgentRunner._coerce_item_to_text(part) for part in content)
                if piece
            ]
            if pieces:
                return "".join(pieces)

        text_attr = getattr(item, "text", None)
        if isinstance(text_attr, str) and text_attr.strip():
            return text_attr

        # Some response objects expose a 'value' field with text
        value_attr = getattr(item, "value", None)
        if isinstance(value_attr, str) and value_attr.strip():
            return value_attr

        return None

    @staticmethod
    def _safe_preview(value: Any, max_len: int = 800) -> Optional[str]:
        """Generate a safe, truncated string preview for logging."""
        if value is None:
            return None
        try:
            text = repr(value)
        except Exception:
            text = f"<unrepresentable {type(value).__name__}>"
        if len(text) > max_len:
            return f"{text[:max_len]}... (truncated {len(text) - max_len} chars)"
        return text

    @staticmethod
    def _collect_guardrail_context(exception: Exception) -> Dict[str, str]:
        """Collect useful attributes from a guardrail exception for debugging."""
        context: Dict[str, str] = {}
        candidate_attrs = [
            "raw_output",
            "validated_output",
            "output",
            "response",
            "failures",
            "failure",
            "errors",
            "metadata",
            "validator",
            "schema",
        ]
        for attr in candidate_attrs:
            if hasattr(exception, attr):
                value = getattr(exception, attr)
                if value:
                    context[attr] = AgentRunner._safe_preview(value)

        # Include args if present
        if getattr(exception, "args", None):
            context["args"] = AgentRunner._safe_preview(exception.args)

        # Include any additional non-callable public attributes
        if hasattr(exception, "__dict__"):
            for key, value in exception.__dict__.items():
                if key.startswith("_") or key in context:
                    continue
                context[key] = AgentRunner._safe_preview(value)

        return {k: v for k, v in context.items() if v}

    @staticmethod
    def extract_tool_result(result: Any) -> Optional[Any]:
        """Extract tool call result from agent response.
        
        Args:
            result: The result from agent.run()
            
        Returns:
            The extracted tool result content, or None if not found
        """
        if hasattr(result, 'messages') and result.messages:
            for message in result.messages:
                if hasattr(message, 'tool_results') and message.tool_results:
                    for tool_result in message.tool_results:
                        if hasattr(tool_result, 'content'):
                            return tool_result.content
        return None
    
    @staticmethod
    def extract_text_response(result: Any) -> Optional[str]:
        """Extract text response from agent result.
        
        Args:
            result: The result from agent.run()
            
        Returns:
            The extracted text response, or None if not found
        """
        if result is None:
            return None

        # Prefer the structured final_output, if present.
        if hasattr(result, "final_output") and result.final_output is not None:
            extracted = AgentRunner._coerce_item_to_text(result.final_output)
            if extracted:
                return extracted

        # Many agent results expose the generated items list; try harvesting text from it.
        new_items = getattr(result, "new_items", None)
        if new_items:
            try:
                from agents.items import ItemHelpers  # type: ignore

                text = ItemHelpers.text_message_outputs(new_items)  # type: ignore[union-attr]
                if text:
                    return text
            except Exception:  # noqa: BLE001
                pass

            for item in new_items:
                extracted = AgentRunner._coerce_item_to_text(item)
                if extracted:
                    return extracted

        # Fall back to message content lists
        if hasattr(result, "messages") and result.messages:
            for message in result.messages:
                extracted = AgentRunner._coerce_item_to_text(message)
                if extracted:
                    return extracted

        if isinstance(result, str):
            return result

        return None
    
    @staticmethod
    def extract_structured_output(result: Any) -> Optional[Any]:
        """Extract structured output from agent response, trying tool results first, then parsing text as JSON.
        
        Args:
            result: The result from agent.run()
            
        Returns:
            The extracted structured data (dict), or None if not found
        """
        import json
        
        # First try to get tool result
        tool_result = AgentRunner.extract_tool_result(result)
        if tool_result:
            return tool_result
        
        # If no tool result, try to parse text response as JSON
        text_response = AgentRunner.extract_text_response(result)
        if text_response:
            try:
                # Try to extract JSON from the text
                # Handle cases where model returns explanation with JSON
                if '{' in text_response and '}' in text_response:
                    # Find the JSON part
                    start = text_response.find('{')
                    end = text_response.rfind('}') + 1
                    json_str = text_response[start:end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse text response as JSON: {text_response[:200]}")
        
        return None
