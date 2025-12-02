"""Streaming LLM client for real-time text generation.

Provides streaming and non-streaming completion methods for LLM providers.
"""

import logging
from typing import AsyncGenerator, Optional

from gaia.infra.llm.model_manager import get_model_provider_for_resolved_model

logger = logging.getLogger(__name__)


class StreamingLLMClient:
    """Client for streaming LLM completions.

    Supports both streaming and non-streaming generation using OpenAI-compatible APIs.
    """

    async def stream_completion(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream completion chunks from LLM.

        Args:
            prompt: The prompt to complete
            model: Model identifier (e.g., "parasail-kimi-k2-instruct-0905")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            str: Text chunks as they're generated
        """
        try:
            # Get provider for this model
            provider = get_model_provider_for_resolved_model(model)

            # Get OpenAI client from provider
            client = provider.client

            logger.info(
                f"🌊 Starting streaming completion: model={model}, temp={temperature}"
            )

            # Create streaming completion
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            stream = await client.chat.completions.create(**kwargs)

            # Yield chunks as they arrive
            chunk_count = 0
            total_chars = 0

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        chunk_count += 1
                        total_chars += len(delta.content)
                        yield delta.content

            logger.info(
                f"✅ Streaming complete: {chunk_count} chunks, {total_chars} chars"
            )

        except Exception as e:
            logger.error(f"❌ Error in streaming completion: {e}", exc_info=True)
            raise

    async def complete(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate non-streaming completion from LLM.

        Args:
            prompt: The prompt to complete
            model: Model identifier (e.g., "parasail-kimi-k2-instruct-0905")
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Complete generated text
        """
        try:
            # Get provider for this model
            provider = get_model_provider_for_resolved_model(model)

            # Get OpenAI client from provider
            client = provider.client

            logger.info(
                f"📝 Generating completion: model={model}, temp={temperature}"
            )

            # Create non-streaming completion
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
            }

            if max_tokens:
                kwargs["max_tokens"] = max_tokens

            response = await client.chat.completions.create(**kwargs)

            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content or ""
                logger.info(f"✅ Completion generated: {len(content)} chars")
                return content

            logger.warning("⚠️ Empty response from LLM")
            return ""

        except Exception as e:
            logger.error(f"❌ Error in completion: {e}", exc_info=True)
            raise


# Singleton instance
streaming_llm_client = StreamingLLMClient()
