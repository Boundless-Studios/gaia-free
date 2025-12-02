#!/usr/bin/env python3
"""
Gaia D&D Campaign Manager - Unified Cross-Platform Startup Script
Combines virtual environment setup, dependency installation, and application startup
"""

import os
import sys
import subprocess
import time
import signal
import platform
from pathlib import Path
import json
import webbrowser
from typing import List

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

# TODO Clean up the environment variable stuff in this file 

# Utility functions
def is_wsl() -> bool:
    """Detect if running in WSL environment."""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except (FileNotFoundError, OSError):
        return False

def get_wsl_ip() -> str | None:
    """Get WSL IP address for backend communication."""
    if not is_wsl():
        return None
    
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None

# Try to import psutil, install if missing
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Installing...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psutil"])
        import psutil
        PSUTIL_AVAILABLE = True
    except subprocess.CalledProcessError:
        print("Warning: Could not install psutil. Process management will be limited.")
        PSUTIL_AVAILABLE = False

class GaiaStartup:
    def __init__(self):
        # Since we're now in src/main.py, need to go up one level to get repo root
        self.repo_root = Path(__file__).parent.parent
        self.src_dir = Path(__file__).parent
        self.frontend_dir = self.src_dir / "frontend"
        self.backend_dir = self.src_dir
        self.processes: List[subprocess.Popen] = []
        self.running = True
        self.is_windows = platform.system() == "Windows"
        self.pid_file = self.repo_root / "gaia.pid"
        
    def log(self, message: str):
        """Print a formatted log message."""
        print(f"[Gaia] {message}")
    
    def check_prerequisites(self) -> bool:
        """Check if required tools are available."""
        # No longer checking for Node.js/npm as they're not required for backend
        # Frontend can be run separately if needed
        return True
    
    def cleanup_existing_processes(self):
        """Kill any existing Gaia processes from PID file."""
        if not self.pid_file.exists():
            self.log("No existing PID file found")
            return
        
        if not PSUTIL_AVAILABLE:
            self.log("psutil not available, skipping process cleanup")
            return
        
        try:
            with open(self.pid_file, 'r') as f:
                pids = json.load(f)
            
            killed_count = 0
            for pid in pids:
                try:
                    proc = psutil.Process(pid)
                    if proc.is_running():
                        self.log(f"Killing existing process {pid}")
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Remove the PID file after cleanup
            self.pid_file.unlink()
            
            if killed_count > 0:
                self.log(f"Killed {killed_count} existing processes")
                time.sleep(2)  # Give processes time to die
            else:
                self.log("No running processes from PID file")
                
        except Exception as e:
            self.log(f"Error cleaning up existing processes: {e}")
    
    def save_pid_file(self):
        """Save process IDs to a file for cleanup."""
        pids = []
        for proc in self.processes:
            if proc.poll() is None:  # Process is still running
                pids.append(proc.pid)
        
        try:
            with open(self.pid_file, 'w') as f:
                json.dump(pids, f)
        except Exception as e:
            self.log(f"Warning: Could not save PID file: {e}")
    
    def install_frontend_dependencies(self) -> bool:
        """Install frontend dependencies."""
        self.log("Installing frontend dependencies...")
        
        # Configure npm for WSL if needed
        if is_wsl():
            try:
                subprocess.run(["npm", "config", "set", "unsafe-perm", "true"], capture_output=True)
                subprocess.run(["npm", "config", "set", "cache", "/tmp/.npm"], capture_output=True)
                self.log("✅ npm configured for WSL")
            except Exception as e:
                self.log(f"⚠️ npm configuration warning: {e}")
        
        # Install dependencies
        try:
            subprocess.run(["npm", "install"], cwd=self.frontend_dir, check=True, capture_output=True)
            self.log("✅ Frontend dependencies installed")
            return True
        except subprocess.CalledProcessError as e:
            self.log(f"❌ npm install failed: {e}")
            return False
    
    def start_backend(self):
        """Start the FastAPI backend server with auto-reload."""
        self.log("Starting backend server with auto-reload and audio enabled...")
        
        try:
            # Use current python (already in venv) with the wrapper script
            cmd = [sys.executable, str(self.repo_root / "run_uvicorn.py")]
            
            # Create environment with proper Python path and audio settings
            env = os.environ.copy()
            # Set PYTHONPATH to include both the project root and src directory
            current_pythonpath = env.get("PYTHONPATH", "")
            project_root = str(self.repo_root)
            src_dir = str(self.backend_dir)
            
            if current_pythonpath:
                env["PYTHONPATH"] = f"{project_root}:{src_dir}:{current_pythonpath}"
            else:
                env["PYTHONPATH"] = f"{project_root}:{src_dir}"
            
            # Also set PYTHONPATH as a separate environment variable that Uvicorn can use
            env["UVICORN_PYTHONPATH"] = env["PYTHONPATH"]
            
            # Ensure client audio stays enabled unless explicitly disabled
            env.pop("GAIA_AUDIO_DISABLED", None)
            env.setdefault("AUTO_TTS_OUTPUT", "windows")  # Use Windows audio in WSL
            
            # CUDNN/WhisperX configuration removed - using ElevenLabs STT instead
            
            # Start the process
            if self.is_windows:
                # On Windows, use CREATE_NEW_PROCESS_GROUP to allow proper cleanup
                process = subprocess.Popen(
                    cmd, 
                    cwd=self.repo_root,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # On Unix, use process group for proper cleanup
                process = subprocess.Popen(
                    cmd, 
                    cwd=self.repo_root,
                    env=env,
                    preexec_fn=os.setsid
                )
            
            self.processes.append(process)
            self.log("✅ Backend server started on http://localhost:8000 (with auto-reload)")
            self.log("✅ Auto-TTS enabled with auto-detected audio output")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to start backend: {e}")
            return False
    
    def start_tts_server(self):
        """Start the f5-tts gradio server."""
        self.log("Starting TTS server...")
        
        try:
            # Import the TTS server manager with proper path handling
            import sys
            import os
            # Add the project root to Python path
            project_root = str(self.repo_root)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # TTS server now runs as external service - no local management needed
            self.log("✅ TTS server running as external service (tts-service container)")
            return True
                
        except Exception as e:
            self.log(f"❌ Failed to start TTS server: {e}")
            return False
    
    def start_frontend(self):
        """Start the React frontend development server."""
        self.log("Starting frontend server...")
        
        # Set environment variables for frontend
        env = {**os.environ, "BROWSER": "none"}
        
        wsl_ip = get_wsl_ip()
        if wsl_ip:
            # In WSL, use the WSL IP for backend communication
            backend_url = f"http://{wsl_ip}:8000"
            env["VITE_BACKEND_URL"] = backend_url
            env["VITE_IS_WSL"] = "true"
            self.log(f"WSL detected, backend URL: {backend_url}")
        else:
            # Use localhost for non-WSL environments
            env["VITE_BACKEND_URL"] = "http://localhost:8000"
            env["VITE_IS_WSL"] = "false"
            self.log("Backend URL: http://localhost:8000")
        
        # Use correct npm command based on OS
        npm_cmd = "npm.cmd" if self.is_windows else "npm"
        cmd = [npm_cmd, "run", "dev"]
        
        try:
            if self.is_windows:
                # On Windows, use CREATE_NEW_PROCESS_GROUP for proper cleanup
                process = subprocess.Popen(
                    cmd, 
                    cwd=self.frontend_dir,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # On Unix, use process group for proper cleanup
                process = subprocess.Popen(
                    cmd, 
                    cwd=self.frontend_dir,
                    env=env,
                    preexec_fn=os.setsid
                )
            
            self.processes.append(process)
            self.log("✅ Frontend server started on http://localhost:3000")
            return True
            
        except Exception as e:
            self.log(f"❌ Failed to start frontend: {e}")
            return False
    
    def wait_for_servers(self):
        """Wait for all servers to be ready."""
        import requests
        
        self.log("Waiting for servers to be ready...")
        
        # Wait for TTS server
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get("http://localhost:7860/", timeout=1)
                if response.status_code == 200:
                    self.log("✅ TTS server is ready")
                    break
            except:
                time.sleep(1)
        else:
            self.log("⚠️  TTS server may not be ready yet")
        
        # Wait for backend
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get("http://localhost:8000/api/health", timeout=1)
                if response.status_code == 200:
                    self.log("✅ Backend is ready")
                    break
            except:
                time.sleep(1)
        else:
            self.log("⚠️  Backend may not be ready yet")
        
        # Wait for frontend
        for i in range(30):  # Wait up to 30 seconds
            try:
                response = requests.get("http://localhost:3000", timeout=1)
                if response.status_code == 200:
                    self.log("✅ Frontend is ready")
                    break
            except:
                time.sleep(1)
        else:
            self.log("⚠️  Frontend may not be ready yet")
    
    def open_browser(self):
        """Open the application in the default browser."""
        self.log("Opening application in browser...")
        time.sleep(2)  # Give servers a moment to fully start
        
        if is_wsl():
            # In WSL, try to use Windows browser via wslview or cmd.exe
            self.log("WSL detected, trying Windows browser...")
            try:
                # Try wslview first (WSL2)
                subprocess.run(['wslview', 'http://localhost:3000'], check=True)
                self.log("✅ Browser opened")
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                try:
                    # Try cmd.exe with start command
                    subprocess.run(['cmd.exe', '/c', 'start', 'http://localhost:3000'], check=True)
                    self.log("✅ Browser opened")
                    return
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.log("Please manually open: http://localhost:3000")
                    return
        
        # Fallback to standard webbrowser module
        try:
            webbrowser.open("http://localhost:3000")
            self.log("✅ Browser opened")
        except Exception:
            self.log("Please manually open: http://localhost:3000")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.log("Shutting down...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clean up running processes with proper cross-platform handling."""
        self.log("Cleaning up processes...")
        
        for process in self.processes:
            try:
                if process.poll() is None:  # Process is still running
                    self.log(f"Terminating process {process.pid}")
                    
                    if self.is_windows:
                        # On Windows, terminate the process group
                        try:
                            process.terminate()
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                    else:
                        # On Unix, kill the process group
                        try:
                            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # Process already dead
                            
            except Exception as e:
                self.log(f"Error cleaning up process {process.pid}: {e}")
                try:
                    process.kill()
                except:
                    pass
        
        # Also kill any remaining processes using psutil (if available)
        if PSUTIL_AVAILABLE:
            self.cleanup_existing_processes()
        
        # Clean up TTS server
        try:
            import sys
            # Add the project root to Python path
            project_root = str(self.repo_root)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            # TTS server cleanup handled by external service
        except Exception as e:
            self.log(f"Warning: Could not cleanup TTS server: {e}")
        
        # Clean up PID file
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except:
                pass
        
        self.log("✅ Cleanup complete")

    def run(self):
        """Main setup and run method."""
        self.log("🎲 Starting Gaia D&D Campaign Manager...")
        
        # Check prerequisites (npm/node already verified by launcher)
        if not self.check_prerequisites():
            return False
        
        # Clean up any existing processes from previous runs
        self.cleanup_existing_processes()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        if not self.is_windows:
            signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Install frontend dependencies
        if not self.install_frontend_dependencies():
            return False

        # Start TTS server
        if not self.start_tts_server():
            return False
        
        # Start servers
        if not self.start_backend():
            return False
        
        if not self.start_frontend():
            return False
        
        # Save PID file for cleanup
        self.save_pid_file()
        
        self.log("Starting server and browser")
        # Wait for servers and open browser
        self.wait_for_servers()
        self.open_browser()
        
        self.log("✅ Gaia is running!")
        self.log("Frontend: http://localhost:3000")
        self.log("Backend API: http://localhost:8000")
        self.log("TTS Server: http://localhost:7860")
        self.log("API Docs: http://localhost:8000/docs")
        self.log("")
        self.log("Backend auto-reload: ON (watches Python files)")
        self.log("Frontend auto-reload: ON (watches React files)")
        self.log("TTS Server: Running on port 7860")
        self.log("")
        self.log("Press Ctrl+C to stop all servers")
        
        # Keep running until interrupted
        try:
            while self.running:
                # Check if processes are still alive
                alive_processes = []
                for proc in self.processes:
                    if proc.poll() is None:
                        alive_processes.append(proc)
                    else:
                        self.log(f"Process {proc.pid} has died")
                
                if not alive_processes:
                    self.log("All processes have died, exiting...")
                    break
                
                self.processes = alive_processes
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("Received interrupt signal")
        finally:
            self.cleanup()
        
        return True

def main():
    """Main entry point."""
    startup = GaiaStartup()
    success = startup.run()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 
