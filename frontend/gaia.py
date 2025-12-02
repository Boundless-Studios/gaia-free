#!/usr/bin/env python3
"""
Gaia Launcher - Docker-based launcher with CLI interface

This script manages the Gaia application using Docker containers.
Commands:
  python gaia_launcher.py start  - Build and start the application
  python gaia_launcher.py stop   - Stop and remove containers
"""

import sys
import subprocess
import platform
import shutil
import argparse
from pathlib import Path
from datetime import datetime


def log(message: str):
    """Print a formatted log message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [Gaia] {message}")


def check_command_exists(cmd: str) -> bool:
    """Check if a Docker command is available."""
    return shutil.which(cmd) is not None


def get_docker_compose_cmd() -> list[str]:
    """Get the correct docker compose command for the platform.
    
    Returns:
        List of command parts: ['docker-compose'] for macOS, ['docker', 'compose'] for WSL
    """
    if platform.system() == "Darwin":
        return ["docker-compose"]
    else:
        # WSL and other Linux systems use 'docker compose' (no hyphen)
        return ["docker", "compose"]


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    elif "microsoft" in platform.uname().release.lower():  # WSL
        try:
            result = subprocess.run(
                ["sudo", "systemctl", "status", "docker"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

def get_docker_install_instructions() -> str:
    """Get OS-specific Docker installation instructions."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return """
Install Docker and Colima (CLI-only, no GUI):
  brew install docker docker-compose colima
  colima start --cpu 4 --memory 8
"""
    
    elif "microsoft" in platform.uname().release.lower():  # WSL
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
    """Check if Docker and docker-compose are available and running."""
    log("Checking Docker dependencies...")
    
    # Check for docker command
    if not check_command_exists("docker"):
        log("❌ Docker command not found")
        print(get_docker_install_instructions())
        return False
    
    # Check for docker-compose command (only on macOS)
    if platform.system() == "Darwin":  # macOS
        if not check_command_exists("docker-compose"):
            log("❌ docker-compose command not found")
            print("\nPlease install docker-compose:")
            print("  brew install docker-compose")
            return False
    
    # Check if Docker daemon is running
    if not check_docker_running():
        log("❌ Docker daemon is not running")
        
        if platform.system() == "Darwin":
            print("  colima start --cpu 4 --memory 8")
        elif "microsoft" in platform.uname().release.lower():
            print("  sudo systemctl start docker")
        else:
            print("  Unsupported platform")
        
        return False
    
    log("✅ Docker is installed and running")
    return True


def start_gaia(args):
    """Start Gaia using Docker Compose."""
    root_dir = Path(__file__).parent
    
    # Check Docker dependencies
    if not check_docker_dependencies():
        return 1
    
    # Check for .settings.docker.env and create from settings.env if needed
    docker_settings = root_dir / ".settings.docker.env"
    if not docker_settings.exists():
        settings_template = root_dir / "settings.env"
        if settings_template.exists():
            log("📝 Creating .settings.docker.env from settings.env template")
            shutil.copy(settings_template, docker_settings)
            log("✅ Created .settings.docker.env - add your API keys to this file")
        else:
            log("❌ No settings.env template found")
            return 1
    
    try:
        # Always build if --force-build is specified
        if args.force_build:
            log("🔨 Force building Docker images...")
            
            # Build with docker-compose
            compose_cmd = get_docker_compose_cmd()
            result = subprocess.run(
                compose_cmd + ["build"],
                cwd=root_dir,
                text=True
            )
            
            if result.returncode != 0:
                log("❌ Docker build failed")
                return 1
            
            log("✅ Docker images built successfully")
        
        # Start containers
        log("🚀 Starting Gaia...")
        
        # Use detached mode by default
        base_cmd = get_docker_compose_cmd()
        compose_cmd = base_cmd + ["up", "-d"]
        if args.logs:
            # If logs requested, run in foreground
            compose_cmd = base_cmd + ["up"]
        
        result = subprocess.run(compose_cmd, cwd=root_dir)
        
        if result.returncode != 0:
            log("❌ Failed to start containers")
            return 1
        
        if not args.logs:
            log("✅ Gaia is running!")
            log("")
            log("🌐 Access points:")
            log("   Frontend: http://localhost:3000")
            log("   Backend API: http://localhost:8000")
            log("   API Health: http://localhost:8000/api/health")
            log("")
            log("📋 Useful commands:")
            compose_cmd_str = " ".join(get_docker_compose_cmd())
            log(f"   View logs: {compose_cmd_str} logs -f")
            log("   Stop Gaia: python gaia_launcher.py stop")
            log("   Restart with logs: python gaia_launcher.py start --logs")
        
        return 0
        
    except KeyboardInterrupt:
        log("\n🛑 Interrupted by user")
        return 1
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


def stop_gaia(args):
    """Stop Gaia containers."""
    root_dir = Path(__file__).parent
    
    log("🛑 Stopping Gaia...")
    
    try:
        # Stop and remove containers
        compose_cmd = get_docker_compose_cmd()
        result = subprocess.run(
            compose_cmd + ["down"],
            cwd=root_dir,
            text=True
        )
        
        if result.returncode != 0:
            log("❌ Failed to stop containers")
            return 1
        
        log("✅ Gaia stopped successfully")
        return 0
        
    except Exception as e:
        log(f"❌ Error: {e}")
        return 1


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Gaia D&D Campaign Manager - Docker Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gaia_launcher.py start               # Start Gaia in background
  python gaia_launcher.py start --logs        # Start with live logs
  python gaia_launcher.py start --force-build # Force rebuild images
  python gaia_launcher.py stop                # Stop Gaia
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start Gaia")
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
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())