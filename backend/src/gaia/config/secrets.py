import os
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SecretsCache:
    """In-memory cache for secrets fetched at container startup.

    By default, this does nothing unless configured via environment variables.
    This avoids repeated calls to Google Secret Manager by pulling secrets
    once during startup and keeping them in memory for the lifetime of the
    container.

    Configuration (all optional):
      - `SECRETS_ON_STARTUP`: Comma-separated entries of the form
          `ENV_VAR=secret_name[@version]` or
          `ENV_VAR=projects/<proj>/secrets/<name>/versions/<version>`
        Example: "OPENAI_API_KEY=openai_key@latest,DB_PASSWORD=db-pass@5"
      - `GCP_PROJECT_ID` or `GOOGLE_CLOUD_PROJECT`: Used when only `secret_name`
        is supplied (not a fully-qualified resource).
      - `GCP_SECRETS_VERSION`: Default version (e.g., `latest`) to use when
        not specified inline via `@version`.

    Notes:
      - If `google-cloud-secret-manager` is not installed or credentials are
        unavailable, this module logs a warning and skips fetching.
      - Fetched secrets are placed into both the cache and `os.environ` to
        maximize compatibility with existing code that reads environment vars.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self._initialized: bool = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._cache.get(key, os.getenv(key, default))

    def _parse_mapping(self, item: str) -> Optional[Tuple[str, str]]:
        """Parse a single mapping item like `ENV_VAR=name@version`.

        Returns (env_var, resource_or_name). Whitespace around items is ignored.
        """
        if not item:
            return None
        if "=" not in item:
            logger.warning("Invalid SECRETS_ON_STARTUP entry (missing '='): %s", item)
            return None
        env_var, spec = item.split("=", 1)
        env_var = env_var.strip()
        spec = spec.strip()
        if not env_var or not spec:
            logger.warning("Invalid SECRETS_ON_STARTUP entry: %s", item)
            return None
        return env_var, spec

    def _to_resource(self, spec: str) -> Optional[str]:
        """Turn `name[@version]` or fully-qualified resource into a resource path.

        If `spec` already looks like a resource path, return it as-is.
        Otherwise, use `GCP_PROJECT_ID`/`GOOGLE_CLOUD_PROJECT` and
        `GCP_SECRETS_VERSION` (default `latest`).
        """
        if spec.startswith("projects/"):
            return spec

        project = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project:
            logger.warning(
                "Cannot resolve secret '%s' without GCP_PROJECT_ID/GOOGLE_CLOUD_PROJECT",
                spec,
            )
            return None

        if "@" in spec:
            name, version = spec.split("@", 1)
        else:
            name, version = spec, os.getenv("GCP_SECRETS_VERSION", "latest")

        name = name.strip()
        version = version.strip()
        if not name or not version:
            logger.warning("Invalid secret spec '%s' (empty name/version)", spec)
            return None

        return f"projects/{project}/secrets/{name}/versions/{version}"

    def initialize_from_gcp(self) -> None:
        """Fetch configured secrets from GCP Secret Manager into memory and env.

        Safe to call multiple times; only runs once per process.
        """
        if self._initialized:
            return

        configured = (os.getenv("SECRETS_ON_STARTUP") or "").strip()
        if not configured:
            logger.info("Secrets startup cache disabled (SECRETS_ON_STARTUP not set)")
            self._initialized = True
            return

        try:
            # Import lazily so the package is optional
            from google.cloud import secretmanager  # type: ignore
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "google-cloud-secret-manager not available; skipping secrets fetch (%s)",
                exc,
            )
            self._initialized = True
            return

        items = [i.strip() for i in configured.split(",") if i.strip()]
        if not items:
            logger.info("SECRETS_ON_STARTUP provided but empty after parsing; skipping")
            self._initialized = True
            return

        client = None
        fetched = 0
        for raw in items:
            parsed = self._parse_mapping(raw)
            if not parsed:
                continue
            env_var, spec = parsed
            resource = self._to_resource(spec)
            if not resource:
                continue
            try:
                if client is None:
                    client = secretmanager.SecretManagerServiceClient()
                resp = client.access_secret_version(name=resource)
                value = resp.payload.data.decode("utf-8")
                self._cache[env_var] = value
                os.environ[env_var] = value  # expose to code using os.getenv
                fetched += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to fetch secret for %s (%s): %s", env_var, resource, exc)

        logger.info("Secrets cache initialized; fetched %d secret(s) at startup", fetched)
        self._initialized = True


# Global cache instance
secrets_cache = SecretsCache()


def init_secrets_cache_from_gcp_if_configured() -> None:
    """Initialize the secrets cache from GCP once, if configured.

    Intended to be called during app startup (e.g., FastAPI lifespan), so that
    secrets are retrieved a single time per container and then served from
    memory thereafter.
    """
    try:
        secrets_cache.initialize_from_gcp()
    except Exception as exc:  # noqa: BLE001
        # Defensive: never fail app startup purely due to optional secrets caching
        logger.warning("Secrets cache initialization skipped due to error: %s", exc)

