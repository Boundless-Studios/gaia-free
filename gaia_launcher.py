#!/usr/bin/env python3
"""
Gaia Launcher - Docker-based launcher with CLI interface

This script manages the Gaia application using Docker containers.
Commands:
  python gaia_launcher.py start       - Start development environment
  python gaia_launcher.py stop        - Stop and remove containers
  python gaia_launcher.py test        - Run test suites (don't run inside docker)
"""

import sys
import subprocess
import platform
import shutil
import argparse
# import webbrowser
# import time
from pathlib import Path
from datetime import datetime

GAIA_BACKEND_SUBMODULE = "backend/"
GAIA_FRONTEND_SUBMODULE = "frontend/"

def log(message: str):
    """Print a formatted log message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [Gaia] {message}")


def is_wsl() -> bool:
    """Detect if running in WSL environment."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except (FileNotFoundError, OSError):
        return False


def check_command_exists(cmd: str) -> bool:
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        # Try docker info - works on all platforms without sudo
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_docker_install_instructions() -> str:
    """Get OS-specific Docker installation instructions."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return """
Install Docker and Colima:
  $ brew install docker docker-compose docker-buildx colima

  add "cliPluginsExtraDirs" to ~/.docker/config.json:
  "cliPluginsExtraDirs": [
      "/opt/homebrew/lib/docker/cli-plugins"
  ]

  $ colima start --cpu 8 --memory 8
"""
    
    elif is_wsl():
        return """
Install Docker in WSL:
  sudo apt update && sudo apt install -y docker.io docker-compose
  sudo usermod -aG docker $USER
  sudo service docker start
Log out and back in for group changes
"""
    
    else:
        return "Unsupported platform. Please use macOS or WSL2."


def check_docker_dependencies() -> bool:
    """Check if Docker is available and running."""
    log("Checking Docker dependencies...")
    
    # Check for docker command
    if not check_command_exists("docker"):
        log("❌ Docker command not found")
        print(get_docker_install_instructions())
        return False
    
    # Check if Docker daemon is running
    if not check_docker_running():
        log("❌ Docker daemon is not running")
        
        if platform.system() == "Darwin":
            print("  colima start --cpu 8 --memory 8")
        elif is_wsl():
            print("  sudo systemctl start docker")
        else:
            print("  Unsupported platform")
        
        return False
    
    log("✅ Docker is installed and running")
    return True


def start_gaia(args):
    """Start Gaia using Docker Compose."""
    root_dir = Path(__file__).parent
    
    # Set up instance-specific environment
    instance = getattr(args, 'instance', 1)
    
    # Determine ports based on instance
    if instance == 1:
        backend_port = 8000
        frontend_port = 3000
        stt_port = 8001
        postgres_port = 5432
    elif instance == 2:
        backend_port = 9000
        frontend_port = 5174
        stt_port = 9001
        postgres_port = 5433
    else:
        # Custom instance - use calculated ports
        backend_port = 8000 + (instance - 1) * 1000
        frontend_port = 3000 + (instance - 1) * 1000
        stt_port = 8001 + (instance - 1) * 1000
        postgres_port = 5432 + instance - 1
    
    # Check and initialize campaign_storage submodule only (others are now subtrees)
    campaign_storage_path = root_dir / "campaign_storage"
    if not campaign_storage_path.exists() or not (campaign_storage_path / ".git").exists():
        log("📦 Initializing campaign_storage submodule...")
        result = subprocess.run(
            ["git", "submodule", "update", "--init", "campaign_storage"],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            log("❌ Failed to initialize campaign_storage submodule")
            log(f"   Error: {result.stderr}")
            return 1
        log("✅ Campaign storage submodule initialized")

    # Check Docker dependencies
    if not check_docker_dependencies():
        return 1

    # Ensure docker_mount directories exist with proper permissions
    docker_mount_dir = root_dir / GAIA_BACKEND_SUBMODULE / "docker_mount"
    tts_temp_dir = docker_mount_dir / "tts_temp"

    # Create necessary directories
    for dir_path in [docker_mount_dir,
                     docker_mount_dir / "logs",
                     docker_mount_dir / "images",
                     docker_mount_dir / "audio",
                     tts_temp_dir]:
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            # Make directories writable
            dir_path.chmod(0o755)
        except PermissionError:
            log(f"⚠️  Warning: Could not create/modify {dir_path}")
            log("   You may need to manually create this directory or run with appropriate permissions")
    
    # Determine environment/profile
    env = args.env or "dev"
    compose_cmd = ["docker", "compose"]
    
    # Add instance-specific env file if not default instance
    if instance != 1:
        instance_env_file = root_dir / f".env.instance{instance}"
        if instance_env_file.exists():
            compose_cmd += ["--env-file", str(instance_env_file)]
            log(f"📋 Using instance configuration: .env.instance{instance}")
        else:
            log(f"⚠️  Warning: .env.instance{instance} not found, using dynamic ports")
            # Set environment variables dynamically
            import os
            os.environ['BACKEND_PORT'] = str(backend_port)
            os.environ['FRONTEND_PORT'] = str(frontend_port)
            os.environ['STT_PORT'] = str(stt_port)
            os.environ['POSTGRES_PORT'] = str(postgres_port)
            os.environ['GAIA_INSTANCE'] = str(instance)
    
    # Add profile
    compose_cmd += ["--profile", env]
    
    try:
        # Always build if --force-build is specified
        if args.force_build:
            log(f"🔨 Force building Docker images for {env} (no cache)...")
            
            result = subprocess.run(
                compose_cmd + ["build", "--no-cache"],
                cwd=root_dir,
                text=True
            )
            
            if result.returncode != 0:
                log("❌ Docker build failed")
                return 1
            
            log("✅ Docker images built successfully")
        
        # Start containers
        log(f"🚀 Starting Gaia in {env} mode...")
        
        if args.logs:
            # If logs requested, run in foreground
            compose_cmd += ["up", "--remove-orphans"]
            result = subprocess.run(compose_cmd, cwd=root_dir)
        else:
            # Use detached mode by default
            compose_cmd += ["up", "-d", "--remove-orphans"]
            result = subprocess.run(compose_cmd, cwd=root_dir, capture_output=True, text=True)
        
        if result.returncode != 0:
            log("❌ Failed to start containers")
            # Show the actual error output
            if result.stdout:
                log(f"stdout: {result.stdout}")
            if result.stderr:
                log(f"stderr: {result.stderr}")
            return 1
        
        if not args.logs:
            log(f"✅ Gaia is running in {env} mode (Instance {instance})!")
            log("")
            log("🌐 Access points:")
            log(f"   Frontend: http://localhost:{frontend_port}")
            log(f"   Backend API: http://localhost:{backend_port}")
            log(f"   API Health: http://localhost:{backend_port}/api/health")
            log(f"   STT Service: ws://localhost:{stt_port}")
            log(f"   PostgreSQL: localhost:{postgres_port}")
            log("")
            log("📋 Useful commands:")
            if instance != 1:
                log(f"   View logs: docker compose --env-file .env.instance{instance} logs -f")
                log(f"   Stop instance: python gaia_launcher.py stop --instance {instance}")
            else:
                log(f"   View logs: docker compose logs -f")
                log("   Stop Gaia: python gaia_launcher.py stop")
            log("   Run tests: python gaia_launcher.py test")
        
        return 0
        
    except KeyboardInterrupt:
        log("\n🛑 Interrupted by user")
        return 1
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


def stop_gaia(args):
    """Stop and remove all Gaia containers and networks."""
    root_dir = Path(__file__).parent
    instance = getattr(args, 'instance', 0)  # 0 means stop all
    
    if instance > 0:
        log(f"🛑 Stopping Gaia instance {instance}...")
    else:
        log("🛑 Stopping all Gaia services...")
    
    try:
        # First, try to stop services using docker-compose in each directory
        compose_dirs = [
            root_dir,
            root_dir / "backend",
            root_dir / "frontend",
            root_dir / "speech-to-text"
        ]
        
        for compose_dir in compose_dirs:
            if (compose_dir / "docker-compose.yml").exists():
                log(f"  Stopping services in {compose_dir.name}...")
                subprocess.run(
                    ["docker", "compose", "down"],
                    cwd=compose_dir,
                    capture_output=True,
                    text=True
                )
        
        # Then, stop any remaining Gaia containers directly
        log("  Stopping any remaining Gaia containers...")
        
        # Get list of running containers with 'gaia' or 'frontend' in the name
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            containers = result.stdout.strip().split('\n')
            if instance > 0:
                # Filter for specific instance
                instance_suffix = f"instance{instance}"
                containers = [c for c in containers 
                             if c and instance_suffix in c.lower()]
            else:
                # Stop all gaia containers
                containers = [c for c in containers 
                             if c and ('gaia' in c.lower() or 'frontend' in c.lower())]
            
            if containers:
                log(f"  Found {len(containers)} container(s) to remove")
                for container in containers:
                    # Stop container
                    subprocess.run(
                        ["docker", "stop", container],
                        capture_output=True,
                        text=True
                    )
                    # Remove container
                    subprocess.run(
                        ["docker", "rm", container],
                        capture_output=True,
                        text=True
                    )
                    log(f"    ✓ Removed: {container}")
        
        # Clean up networks
        log("  Cleaning up Docker networks...")
        result = subprocess.run(
            ["docker", "network", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            networks = [n for n in result.stdout.strip().split('\n')
                       if n and ('gaia' in n.lower() or 'backend' in n.lower() or 'frontend' in n.lower())]
            
            if networks:
                for network in networks:
                    # Skip default network
                    if network != 'bridge':
                        subprocess.run(
                            ["docker", "network", "rm", network],
                            capture_output=True,
                            text=True
                        )
                        log(f"    ✓ Removed network: {network}")
        
        log("✅ All Gaia services stopped and removed successfully")
        return 0
        
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


def test_gaia(args):
    """Run test suites using Docker exec on backend container."""
    root_dir = Path(__file__).parent

    # Check Docker dependencies
    if not check_docker_dependencies():
        return 1

    # Build test command - handle both directory paths and specific test files
    test_path = args.path if hasattr(args, 'path') and args.path else "test/"

    # If test_path doesn't start with "test/" or "/", prepend "test/"
    # This handles cases like "test_combat_full_integration.py" -> "test/test_combat_full_integration.py"
    if not test_path.startswith("/") and not test_path.startswith("test/"):
        # Check if it's just a test file name
        if test_path.endswith(".py"):
            test_path = f"test/{test_path}"

    verbose = "-xvs" if hasattr(args, 'verbose') and args.verbose else "-v"
    grep_pattern = args.grep if hasattr(args, 'grep') and args.grep else None

    # Check which container is running (prefer gpu, fallback to prod, then dev)
    containers = ["gaia-backend-gpu", "gaia-backend-prod", "gaia-backend-dev"]
    running_container = None

    for container in containers:
        check_cmd = ["docker", "ps", "-q", "-f", f"name={container}"]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        if result.stdout.strip():
            running_container = container
            break

    if not running_container:
        log("❌ No Gaia backend container is running")
        log("💡 Start the backend first with: python gaia_launcher.py start")
        return 1

    log(f"🧪 Running tests in {running_container}...")
    if test_path.endswith(".py"):
        log(f"📋 Test file: {test_path}")

    # Build pytest command with secrets loading
    # First decrypt and export secrets, then run pytest
    secrets_setup = """
export SOPS_AGE_KEY=$(cat /run/secrets/age-key.txt 2>/dev/null || echo "")
if [ -n "$SOPS_AGE_KEY" ] && [ -f /home/gaia/secrets/.secrets.env ]; then
    eval "$(sops -d /home/gaia/secrets/.secrets.env 2>/dev/null | grep -v '^#' | grep '=' | sed 's/^/export /')"
fi
"""
    pytest_cmd = f"{secrets_setup}cd /home/gaia && python3 -m pytest {test_path} {verbose}"
    if grep_pattern:
        pytest_cmd += f" -k '{grep_pattern}'"
    if hasattr(args, 'extra') and args.extra:
        pytest_cmd += f" {args.extra}"

    # Show command for transparency
    log(f"📝 Command: pytest {test_path} {verbose}")

    try:
        # Run tests in Docker container
        result = subprocess.run(
            ["docker", "exec", running_container, "bash", "-c", pytest_cmd],
            cwd=root_dir
        )

        if result.returncode != 0:
            log("❌ Tests failed")
            return 1

        log("✅ Tests completed")
        return 0

    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


def update_gaia(args):
    """Update Gaia repository and submodules to latest versions."""
    root_dir = Path(__file__).parent
    
    # Check if git is available
    if not check_command_exists("git"):
        log("❌ Git command not found")
        log("Please install git to use the update feature")
        return 1
    
    # Check if we're in a git repository
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            log("❌ Not in a git repository")
            return 1
    except Exception as e:
        log(f"❌ Error checking git repository: {e}")
        return 1
    
    log("🔄 Updating Gaia repository and submodules...")
    
    try:
        # Fetch latest changes from origin
        log("📡 Fetching latest changes...")
        result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=root_dir,
            text=True
        )
        if result.returncode != 0:
            log("❌ Failed to fetch from origin")
            return 1
        
        # Get current branch name
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            log("❌ Failed to get current branch")
            return 1
        
        current_branch = result.stdout.strip()
        log(f"📋 Current branch: {current_branch}")
        
        # Pull latest changes for current branch
        log(f"⬇️  Pulling latest changes for {current_branch}...")
        result = subprocess.run(
            ["git", "pull", "origin", current_branch],
            cwd=root_dir,
            text=True
        )
        if result.returncode != 0:
            log("❌ Failed to pull latest changes")
            log("💡 You may have uncommitted changes or merge conflicts")
            return 1
        
        # Update subtrees (db, auth, backend, frontend, speech-to-text)
        log("🌳 Updating subtrees...")
        subtrees = [
            ("db", "db-remote"),
            ("auth", "auth-remote"),
            ("backend", "backend-remote"),
            ("frontend", "frontend-remote"),
            ("speech-to-text", "stt-remote")
        ]
        
        for prefix, remote in subtrees:
            log(f"  📥 Pulling {prefix}...")
            result = subprocess.run(
                ["git", "subtree", "pull", f"--prefix={prefix}", remote, "main", "--squash"],
                cwd=root_dir,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                if "no changes" in result.stdout.lower() or "already up to date" in result.stdout.lower():
                    log(f"  ✅ {prefix} is already up to date")
                else:
                    log(f"  ⚠️  Warning: Failed to update {prefix} subtree")
                    log(f"     {result.stderr.strip()}")
            else:
                log(f"  ✅ {prefix} updated")
        
        # Update campaign_storage submodule only
        log("📦 Updating campaign_storage submodule...")
        result = subprocess.run(
            ["git", "submodule", "update", "--init", "--remote", "campaign_storage"],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            log("⚠️  Warning: Failed to update campaign_storage submodule")
            log(f"   {result.stderr.strip()}")
        else:
            # Checkout main branch in campaign_storage to avoid detached HEAD
            result = subprocess.run(
                ["git", "-C", "campaign_storage", "checkout", "main"],
                cwd=root_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                result = subprocess.run(
                    ["git", "-C", "campaign_storage", "pull", "origin", "main"],
                    cwd=root_dir,
                    capture_output=True,
                    text=True
                )
                log("✅ campaign_storage updated")
        
        # Show updated commit info
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            latest_commit = result.stdout.strip()
            log(f"✅ Updated to: {latest_commit}")
        
        log("✅ Gaia repository and subtrees updated successfully!")
        log("")
        log("💡 Consider rebuilding containers to use latest changes:")
        log("   python gaia_launcher.py start --force-build")
        
        return 0
        
    except Exception as e:
        log(f"❌ Error during update: {e}")
        return 1


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Gaia D&D Campaign Manager - Docker Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gaia_launcher.py start               # Start default instance (ports 8000/3000)
  python gaia_launcher.py start --instance 2  # Start instance 2 (ports 9000/5174)
  python gaia_launcher.py start --env prod    # Start production environment
  python gaia_launcher.py stop                # Stop all containers
  python gaia_launcher.py stop --instance 2   # Stop only instance 2
  python gaia_launcher.py test                # Run test suites
  python gaia_launcher.py update              # Update repository and submodules
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start Gaia")
    start_parser.add_argument(
        "--env", "-e",
        choices=["dev", "prod", "gpu"],
        default="dev",
        help="Environment to start (default: dev)"
    )
    start_parser.add_argument(
        "--instance", "-i",
        type=int,
        default=1,
        help="Instance number (1=default ports, 2=secondary ports, etc.)"
    )
    start_parser.add_argument(
        "--logs", "-l",
        action="store_true",
        help="Show live logs (run in foreground)"
    )
    start_parser.add_argument(
        "--force-build", "-f",
        action="store_true",
        help="Force rebuild Docker images"
    )
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop Gaia")
    stop_parser.add_argument(
        "--instance", "-i",
        type=int,
        default=0,
        help="Instance number to stop (0=all instances)"
    )
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run test suites")
    test_parser.add_argument(
        "path",
        nargs="?",
        default="test/",
        help="Test path or file (default: test/)"
    )
    test_parser.add_argument(
        "-k", "--grep",
        help="Only run tests matching this pattern"
    )
    test_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output with full tracebacks"
    )
    test_parser.add_argument(
        "-e", "--extra",
        help="Extra pytest arguments to pass through"
    )
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update repository and submodules")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Default to showing help if no command
    if not args.command:
        parser.print_help()
        return 0
    
    # Execute command
    if args.command == "start":
        return start_gaia(args)
    elif args.command == "stop":
        return stop_gaia(args)
    elif args.command == "test":
        return test_gaia(args)
    elif args.command == "update":
        return update_gaia(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())