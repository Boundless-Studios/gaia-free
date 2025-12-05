"""Cloud Run entrypoint for the Gaia backend.

This script trims the runtime logic down to the essentials required for
serverless execution: ensure storage paths exist, run any pre-start hook, and
launch Uvicorn with environment-driven configuration.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path


def ensure_storage_directory() -> None:
    """Create the campaign storage directory when provided.

    Skip creation if path is not writable (e.g., Cloud Run read-only filesystem).
    Storage should use GCS buckets via CAMPAIGN_STORAGE_BUCKET instead.
    """

    storage_path = os.getenv("CAMPAIGN_STORAGE_PATH")
    if not storage_path:
        return

    path = Path(storage_path)
    # Skip if parent directory is not writable (Cloud Run read-only FS)
    if not os.access(path.parent, os.W_OK):
        print(f"Skipping directory creation for {path} (read-only filesystem)")
        return

    path.mkdir(parents=True, exist_ok=True)
    print(f"Ensured campaign storage directory exists at {path}")


def ensure_pregenerated_content() -> None:
    """Run pregeneration script when required content is missing.

    Checks FORCE_PREGEN environment variable to determine whether to regenerate
    content even if it already exists.
    """

    if os.getenv("SKIP_AUTO_PREGEN", "").lower() in {"1", "true", "yes"}:
        print("Skipping automatic pregenerated content bootstrap (SKIP_AUTO_PREGEN set).")
        return

    storage_path = os.getenv("CAMPAIGN_STORAGE_PATH")
    if not storage_path:
        print("Skipping pregenerated content bootstrap (CAMPAIGN_STORAGE_PATH not set).")
        return

    script_path = Path(__file__).with_name("pregenerate_content.py")
    if not script_path.exists():
        print(f"Pregeneration script not found at {script_path}; skipping bootstrap.")
        return

    # Check FORCE_PREGEN environment variable
    force_pregen = os.getenv("FORCE_PREGEN", "").lower() in {"1", "true", "yes"}

    cmd = [sys.executable, str(script_path)]

    # Only add --if-missing flag if not forcing regeneration
    if not force_pregen:
        cmd.append("--if-missing")

    env_min_campaigns = os.getenv("AUTO_PREGEN_MIN_CAMPAIGNS")
    if env_min_campaigns:
        cmd.append(f"--min-campaigns={env_min_campaigns}")

    env_min_characters = os.getenv("AUTO_PREGEN_MIN_CHARACTERS")
    if env_min_characters:
        cmd.append(f"--min-characters={env_min_characters}")

    env_lock_timeout = os.getenv("AUTO_PREGEN_LOCK_TIMEOUT")
    if env_lock_timeout:
        cmd.append(f"--lock-timeout={env_lock_timeout}")

    if force_pregen:
        print(
            "🔄 Forcing regeneration of pregenerated content (FORCE_PREGEN=true)...",
            flush=True,
        )
    else:
        print(
            "Ensuring pregenerated campaigns and characters are available...",
            flush=True,
        )

    # Pre-generation failures are non-blocking by default (production resilience)
    # Set AUTO_PREGEN_FAIL_ON_ERROR=true to make them blocking (for development/debugging)
    fail_on_error = os.getenv("AUTO_PREGEN_FAIL_ON_ERROR", "").lower() in {"1", "true", "yes"}

    try:
        subprocess.run(cmd, check=True, env=os.environ.copy())
    except subprocess.CalledProcessError as exc:
        error_msg = (
            f"Pregenerated content bootstrap failed with exit code {exc.returncode}. "
            "The application will start, but campaign/character creation may fail if no "
            "pre-generated content exists in storage."
        )

        if fail_on_error:
            print(
                f"❌ ERROR: {error_msg}",
                file=sys.stderr,
                flush=True,
            )
            print(
                "Blocking startup due to pregeneration failure (AUTO_PREGEN_FAIL_ON_ERROR=true)",
                file=sys.stderr,
                flush=True,
            )
            raise
        else:
            print(
                f"⚠️ WARNING: {error_msg}",
                file=sys.stderr,
                flush=True,
            )
            print(
                "Continuing startup anyway (default behavior - set AUTO_PREGEN_FAIL_ON_ERROR=true to block on errors)",
                file=sys.stderr,
                flush=True,
            )


def run_prestart_hook() -> None:
    """Execute an optional prestart command before launching Uvicorn."""

    prestart_command = os.getenv("PRESTART_COMMAND", "").strip()
    if not prestart_command:
        return

    print(f"Running prestart command: {prestart_command}")
    subprocess.run(prestart_command, shell=True, check=True)


def launch_uvicorn() -> None:
    """Start the Uvicorn server with environment-driven settings."""

    port = int(os.getenv("PORT", "8080"))
    workers = os.getenv("WORKERS", "1")
    app_module = os.getenv("APP_MODULE", "gaia.api.app:socket_app")

    uvicorn_args = [
        sys.executable,
        "-m",
        "uvicorn",
        app_module,
        "--host",
        "0.0.0.0",
        "--port",
        str(port),
        "--workers",
        str(workers),
    ]

    print(
        "Starting Uvicorn",
        " ".join(shlex.quote(arg) for arg in uvicorn_args[2:]),
        flush=True,
    )

    os.execvp(uvicorn_args[0], uvicorn_args)


def main() -> None:
    ensure_storage_directory()
    ensure_pregenerated_content()
    run_prestart_hook()
    launch_uvicorn()


if __name__ == "__main__":
    main()
