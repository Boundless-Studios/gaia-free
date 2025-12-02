#!/usr/bin/env python3
"""
Gaia Process Cleanup Script

This script cleans up any existing Gaia processes that may be running.
It checks for:
- Processes tracked in gaia.pid file
- Processes listening on ports 8000 (backend) and 3000 (frontend)

Run this script when you need to force-stop all Gaia processes.
"""

import os
import sys
import subprocess
import platform
import signal
import time
import json
from pathlib import Path


def log(message: str):
    """Print a formatted log message."""
    print(f"[Gaia Cleanup] {message}")


def cleanup_existing_processes(root_dir: Path):
    """Clean up any existing Gaia processes."""
    log("Checking for existing Gaia processes...")
    
    pid_file = root_dir / "gaia.pid"
    
    # First, try to use the PID file if it exists
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                pids = json.load(f)
            
            killed_count = 0
            for pid in pids:
                try:
                    # Check if process exists
                    os.kill(pid, 0)
                    # If we get here, process exists, so kill it
                    log(f"Killing existing process {pid}")
                    os.kill(pid, signal.SIGTERM)
                    killed_count += 1
                except OSError:
                    # Process doesn't exist
                    continue
            
            if killed_count > 0:
                log(f"Killed {killed_count} existing processes")
                time.sleep(2)  # Give processes time to terminate
            
            # Remove PID file
            pid_file.unlink()
            log("Removed PID file")
            
        except Exception as e:
            log(f"Error reading PID file: {e}")
    
    # Also check for processes on specific ports
    if platform.system() != "Windows":
        # Kill processes on ports 8000 (backend) and 3000 (frontend)
        for port in [8000, 3000]:
            try:
                # Use lsof to find process using the port
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            log(f"Killing process {pid} on port {port}")
                            os.kill(int(pid), signal.SIGTERM)
                        except (ValueError, OSError):
                            continue
            except FileNotFoundError:
                # lsof not available, try netstat
                try:
                    result = subprocess.run(
                        ["netstat", "-tlnp"],
                        capture_output=True,
                        text=True
                    )
                    if f":{port}" in result.stdout:
                        log(f"Warning: Port {port} is in use but cannot determine PID")
                except:
                    pass
    else:
        # Windows process cleanup
        try:
            # Kill processes on ports using netstat
            for port in [8000, 3000]:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True,
                    shell=True
                )
                for line in result.stdout.split('\n'):
                    if f":{port}" in line and "LISTENING" in line:
                        # Extract PID from the last column
                        parts = line.split()
                        if parts:
                            try:
                                pid = int(parts[-1])
                                log(f"Killing process {pid} on port {port}")
                                subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
                            except (ValueError, IndexError):
                                continue
        except Exception as e:
            log(f"Error during Windows cleanup: {e}")
    
    log("Cleanup complete")


def main():
    """Main cleanup logic."""
    root_dir = Path(__file__).parent
    
    print("=" * 60)
    print("Gaia Process Cleanup")
    print("=" * 60)
    print()
    
    # Confirm with user
    response = input("This will stop all running Gaia processes. Continue? [y/N]: ").strip().lower()
    if response != 'y':
        log("Cleanup cancelled")
        return
    
    print()
    cleanup_existing_processes(root_dir)
    
    print()
    print("=" * 60)
    print("All Gaia processes have been stopped.")
    print("You can now start Gaia fresh with: ./gaia_launcher.py")
    print("=" * 60)


if __name__ == "__main__":
    main()