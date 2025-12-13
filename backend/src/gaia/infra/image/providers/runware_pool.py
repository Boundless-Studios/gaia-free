"""
Runware Client Pool for Parallel Image Generation

Manages a pool of independent Runware WebSocket clients to enable
concurrent image generation requests.

Each client maintains its own WebSocket connection, allowing true
parallelism instead of serialized requests through a single connection.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from gaia.infra.image.providers.runware import RunwareImageService, RUNWARE_AVAILABLE

logger = logging.getLogger(__name__)


class RunwareClientPool:
    """Pool of Runware clients for parallel image generation.

    The Runware WebSocket API doesn't handle concurrent requests well on a
    single connection. This pool maintains multiple independent clients,
    each with its own WebSocket connection, enabling true parallel generation.

    Usage:
        pool = RunwareClientPool(pool_size=3)

        # Generate 3 images in parallel
        results = await asyncio.gather(
            pool.generate_image(prompt="A forest"),
            pool.generate_image(prompt="A castle"),
            pool.generate_image(prompt="A dragon"),
        )

    Attributes:
        pool_size: Maximum number of concurrent clients/connections
        clients: List of initialized RunwareImageService instances
    """

    DEFAULT_POOL_SIZE = 3

    def __init__(self, pool_size: Optional[int] = None):
        """Initialize the client pool.

        Args:
            pool_size: Number of clients in the pool. Defaults to 3.
                      More clients = more parallelism but more connections.
        """
        self.pool_size = pool_size or self.DEFAULT_POOL_SIZE
        self.clients: List[RunwareImageService] = []
        self._client_locks: List[asyncio.Lock] = []
        self._pool_lock = asyncio.Lock()
        self._initialized = False

        logger.info(f"RunwareClientPool created with pool_size={self.pool_size}")

    def is_available(self) -> bool:
        """Check if Runware is available (SDK installed and API key configured)."""
        # Create a temporary client to check availability
        temp_client = RunwareImageService()
        return temp_client.is_available()

    async def _ensure_initialized(self) -> None:
        """Lazily initialize the client pool on first use."""
        if self._initialized:
            return

        async with self._pool_lock:
            # Double-check after acquiring lock
            if self._initialized:
                return

            logger.info(f"Initializing Runware client pool with {self.pool_size} clients...")

            for i in range(self.pool_size):
                client = RunwareImageService()
                if client.is_available():
                    self.clients.append(client)
                    self._client_locks.append(asyncio.Lock())
                    logger.debug(f"Created Runware client {i + 1}/{self.pool_size}")
                else:
                    logger.warning(f"Could not create Runware client {i + 1} - not available")
                    break

            if self.clients:
                logger.info(f"✅ Runware client pool initialized with {len(self.clients)} clients")
            else:
                logger.warning("⚠️ No Runware clients available in pool")

            self._initialized = True

    async def _get_available_client(self) -> tuple[int, RunwareImageService, asyncio.Lock]:
        """Get the next available client from the pool.

        Uses a simple strategy: try to acquire locks in order, use first available.
        If all are busy, wait for the first one.

        Returns:
            Tuple of (client_index, client, lock)

        Raises:
            RuntimeError: If no clients are available in the pool
        """
        await self._ensure_initialized()

        if not self.clients:
            raise RuntimeError("No Runware clients available in pool")

        # Try to find an immediately available client
        for i, (client, lock) in enumerate(zip(self.clients, self._client_locks)):
            if not lock.locked():
                return (i, client, lock)

        # All clients busy - wait for the first one
        # This ensures fair queuing
        lock = self._client_locks[0]
        return (0, self.clients[0], lock)

    async def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        n: int = 1,
        response_format: str = "b64_json",
        negative_prompt: Optional[str] = None,
        seed: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        num_inference_steps: Optional[int] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate image using next available client from the pool.

        This method is safe to call concurrently - each call will use a
        different client if available, enabling true parallel generation.

        Args:
            prompt: Text description of the image
            width: Image width (default: 1024)
            height: Image height (default: 1024)
            n: Number of images to generate (default: 1)
            response_format: Format of response ("url" or "b64_json")
            negative_prompt: What to avoid in the image
            seed: Random seed for reproducibility
            guidance_scale: How closely to follow the prompt
            num_inference_steps: Number of denoising steps
            model: Model to use
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict containing image generation results with keys:
            - success: bool
            - images: list of generated images
            - provider: "runware"
            - client_index: which pool client was used (for debugging)
        """
        client_idx, client, lock = await self._get_available_client()

        async with lock:
            logger.debug(f"🎨 Pool client {client_idx} generating: {prompt[:50]}...")

            result = await client.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                n=n,
                response_format=response_format,
                negative_prompt=negative_prompt,
                seed=seed,
                guidance_scale=guidance_scale,
                num_inference_steps=num_inference_steps,
                model=model,
                **kwargs
            )

            # Add pool metadata for debugging
            result["_pool_client_index"] = client_idx

            if result.get("success"):
                logger.debug(f"✅ Pool client {client_idx} completed successfully")
            else:
                logger.warning(f"⚠️ Pool client {client_idx} failed: {result.get('error')}")

            return result

    async def generate_images_parallel(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate multiple images in parallel using the pool.

        Convenience method for batch generation. Each request is processed
        by an available client from the pool.

        Args:
            requests: List of dicts, each containing kwargs for generate_image()
                     Example: [{"prompt": "A forest"}, {"prompt": "A castle"}]

        Returns:
            List of results in the same order as requests
        """
        if not requests:
            return []

        logger.info(f"🎨 Generating {len(requests)} images in parallel (pool_size={self.pool_size})")

        tasks = [
            self.generate_image(**request)
            for request in requests
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error dicts
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Image generation {i} failed with exception: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "images": [],
                    "provider": "runware"
                })
            else:
                processed_results.append(result)

        success_count = sum(1 for r in processed_results if r.get("success"))
        logger.info(f"✅ Parallel generation complete: {success_count}/{len(requests)} succeeded")

        return processed_results

    async def disconnect_all(self) -> None:
        """Disconnect all clients in the pool.

        Call this during application shutdown to cleanly close WebSocket connections.
        """
        logger.info("Disconnecting all Runware pool clients...")

        for i, client in enumerate(self.clients):
            try:
                await client.disconnect()
                logger.debug(f"Disconnected pool client {i}")
            except Exception as e:
                logger.warning(f"Error disconnecting pool client {i}: {e}")

        self.clients = []
        self._client_locks = []
        self._initialized = False

        logger.info("All Runware pool clients disconnected")

    def get_pool_status(self) -> Dict[str, Any]:
        """Get current status of the client pool.

        Returns:
            Dict with pool status information
        """
        busy_count = sum(1 for lock in self._client_locks if lock.locked())

        return {
            "pool_size": self.pool_size,
            "initialized": self._initialized,
            "active_clients": len(self.clients),
            "busy_clients": busy_count,
            "available_clients": len(self.clients) - busy_count,
            "sdk_available": RUNWARE_AVAILABLE,
        }


# Singleton pool instance
_runware_pool: Optional[RunwareClientPool] = None


def get_runware_client_pool(pool_size: Optional[int] = None) -> Optional[RunwareClientPool]:
    """Get the singleton Runware client pool instance.

    Args:
        pool_size: Pool size (only used on first call to create the pool)

    Returns:
        RunwareClientPool instance if Runware is available, None otherwise
    """
    global _runware_pool

    if _runware_pool is None:
        _runware_pool = RunwareClientPool(pool_size=pool_size)

    return _runware_pool if _runware_pool.is_available() else None
