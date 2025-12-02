#!/usr/bin/env python3
"""Test runner script for Gaia project."""
import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Check if we need to use virtual environment
root_dir = Path(__file__).parent
if str(root_dir).startswith("/mnt/c"):
    # WSL with Windows filesystem
    import tempfile
    venv_dir = Path(tempfile.gettempdir()) / "gaia_venv"
else:
    venv_dir = root_dir / "venv"

# Use venv Python if available
if venv_dir.exists():
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    
    if venv_python.exists() and sys.executable != str(venv_python):
        # Re-run with venv Python
        cmd = [str(venv_python), __file__] + sys.argv[1:]
        sys.exit(subprocess.call(cmd))

def run_tests(args):
    """Run the test suite."""
    # Set test environment variables
    os.environ["TESTING"] = "true"
    os.environ["USE_SMALLER_MODEL"] = "true"
    os.environ["GAIA_AUDIO_DISABLED"] = "true"

    # Set CAMPAIGN_STORAGE_PATH to a valid temp directory if not already set
    # This prevents failures when config/gcp.env sets it to /mnt/campaigns (which doesn't exist in CI)
    if "CAMPAIGN_STORAGE_PATH" not in os.environ or os.environ["CAMPAIGN_STORAGE_PATH"] == "/mnt/campaigns":
        import tempfile
        test_storage = Path(tempfile.gettempdir()) / "test_campaigns"
        test_storage.mkdir(exist_ok=True)
        os.environ["CAMPAIGN_STORAGE_PATH"] = str(test_storage)
        print(f"📁 Using test campaign storage: {test_storage}")

    # Build pytest command using current Python executable
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    
    # Add coverage
    if args.coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Add specific test paths if provided
    if args.tests:
        cmd.extend(args.tests)
    else:
        cmd.append("test/")
    
    # Add markers
    if args.markers:
        cmd.extend(["-m", args.markers])
    
    # Add other pytest options
    if args.pytest_args:
        cmd.extend(args.pytest_args)
    
    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    return result.returncode

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run Gaia test suite")
    
    parser.add_argument(
        "tests",
        nargs="*",
        help="Specific test files or directories to run"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    parser.add_argument(
        "-m", "--markers",
        help="Run tests matching given mark expression"
    )
    
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only quick unit tests (skip integration tests)"
    )
    
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run only integration tests"
    )
    
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments to pass to pytest"
    )
    
    args = parser.parse_args()
    
    # Handle quick/integration flags
    if args.quick:
        args.markers = "not integration"
    elif args.integration:
        args.markers = "integration"
    
    # Install test dependencies if needed
    try:
        import pytest
    except ImportError:
        print("Installing test dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest", "pytest-cov", "pytest-asyncio"])
    
    # Run tests
    exit_code = run_tests(args)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
