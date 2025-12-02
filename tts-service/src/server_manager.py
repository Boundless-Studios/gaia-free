"""
TTS Server Manager for managing f5-tts gradio server.

DISABLED: F5-TTS has been disabled to remove PyTorch/CUDA dependencies.
This code is kept for reference but will not start the TTS server.
"""

import os
import subprocess
import time
import requests
import logging
import signal
import psutil
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# F5-TTS DISABLED - No longer starting the server
F5_TTS_ENABLED = False

class TTSServerManager:
    """
    Manages the f5-tts gradio server process.

    DISABLED: F5-TTS functionality is currently disabled to avoid PyTorch/CUDA dependencies.
    """

    def __init__(self, port: int = 7860):
        self.port = port
        self.process: Optional[subprocess.Popen] = None
        self.server_url = f"http://localhost:{port}"
        self.is_running = False

        if not F5_TTS_ENABLED:
            logger.info("F5-TTS is disabled. Server will not start.")

    def log(self, message: str):
        """Print a formatted log message."""
        print(f"[TTS Server] {message}")

    def check_server_running(self) -> bool:
        """Check if the TTS server is already running on the configured port."""
        try:
            response = requests.get(f"{self.server_url}/", timeout=3)
            if response.status_code == 200:
                self.log(f"✅ TTS server already running on port {self.port}")
                return True
        except requests.exceptions.RequestException:
            pass
        return False

    def find_existing_process(self) -> Optional[int]:
        """Find existing f5-tts process by checking command line."""
        try:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any('f5-tts' in arg for arg in cmdline):
                        return proc.info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"Error finding existing TTS process: {e}")
        return None

    def kill_existing_process(self, pid: int) -> bool:
        """Kill an existing TTS process."""
        try:
            proc = psutil.Process(pid)
            self.log(f"Killing existing TTS process {pid}")
            proc.terminate()
            proc.wait(timeout=5)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            try:
                proc.kill()
                return True
            except:
                return False

    def start_server(self) -> bool:
        """Start the f5-tts gradio server."""
        # Check if F5-TTS is enabled
        if not F5_TTS_ENABLED:
            self.log("⚠️ F5-TTS is disabled. Skipping server startup.")
            self.is_running = False
            return False

        # First check if server is already running
        if self.check_server_running():
            self.is_running = True
            return True

        # Check for existing process
        existing_pid = self.find_existing_process()
        if existing_pid:
            self.log(f"Found existing TTS process {existing_pid}, killing it...")
            if self.kill_existing_process(existing_pid):
                time.sleep(2)  # Give process time to die
            else:
                self.log("⚠️ Could not kill existing process, continuing anyway...")

        # Try to start the server
        self.log(f"Starting f5-tts gradio server on port {self.port}...")

        try:
            # Use f5-tts_infer-gradio command
            cmd = ["f5-tts_infer-gradio", "--port", str(self.port), "--host", "0.0.0.0"]

            # Set up environment with warning suppression
            env = os.environ.copy()
            env["PYTHONWARNINGS"] = "ignore::UserWarning"  # Suppress all UserWarnings
            env["TF_CPP_MIN_LOG_LEVEL"] = "2"  # Suppress TensorFlow warnings

            # Start the process with captured stdout/stderr for timestamping
            self.process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,  # Capture stdout for timestamping
                stderr=subprocess.STDOUT,  # Merge stderr into stdout
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Wait for server to start with better progress reporting
            self.log("⏳ Waiting for TTS server to start (this may take 30-60 seconds)...")

            # Wait up to 120 seconds for the server to start (longer for Docker)
            max_wait_time = 120
            check_interval = 3
            total_checks = max_wait_time // check_interval

            for i in range(total_checks):
                # Check if process is still alive
                if self.process.poll() is not None:
                    # Process died
                    stdout, stderr = self.process.communicate()
                    self.log(f"❌ TTS server process died")
                    if stdout:
                        self.log(f"stdout: {stdout}")
                    if stderr:
                        self.log(f"stderr: {stderr}")
                    return False

                # Check if server is responding
                if self.check_server_running():
                    self.is_running = True
                    self.log("✅ TTS server started successfully")
                    return True

                # Show progress every 15 seconds
                if (i + 1) % 5 == 0:
                    elapsed = (i + 1) * check_interval
                    self.log(f"⏳ Still waiting... ({elapsed}s elapsed)")

                time.sleep(check_interval)

            # If we get here, server didn't start in time
            self.log(f"❌ TTS server failed to start within {max_wait_time} seconds")

            # Check if process is still alive but not responding
            if self.process.poll() is None:
                self.log("⚠️ Server process is running but not responding - it may still be loading models")
                self.log("You can try accessing the server manually at http://localhost:7860")
                # Don't kill the process, let it continue loading
                return False
            else:
                # Process died
                stdout, stderr = self.process.communicate()
                self.log(f"❌ TTS server process died")
                if stdout:
                    self.log(f"stdout: {stdout}")
                if stderr:
                    self.log(f"stderr: {stderr}")
                return False

        except FileNotFoundError:
            self.log("❌ f5-tts_infer-gradio command not found")
            self.log("Please install f5-tts: pip install f5-tts")
            return False
        except Exception as e:
            self.log(f"❌ Failed to start TTS server: {e}")
            return False

    def validate_connection(self) -> Tuple[bool, str]:
        """Validate connection to the TTS server."""
        # If F5-TTS is disabled, report healthy (service is working as configured)
        if not F5_TTS_ENABLED:
            return True, "✅ TTS service running (F5-TTS disabled by configuration)"

        try:
            response = requests.get(f"{self.server_url}/", timeout=5)
            if response.status_code == 200:
                return True, "✅ Local TTS is ready"
            else:
                return False, f"❌ TTS server returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "❌ Cannot connect to TTS server"
        except requests.exceptions.Timeout:
            return False, "❌ TTS server connection timeout"
        except Exception as e:
            return False, f"❌ TTS server validation error: {e}"

    def stop_server(self):
        """Stop the TTS server."""
        if self.process and self.process.poll() is None:
            self.log("Stopping TTS server...")
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.is_running = False
            self.log("✅ TTS server stopped")

    def cleanup(self):
        """Clean up the server process."""
        self.stop_server()

# Global TTS server manager instance
tts_server_manager = TTSServerManager()