"""TTS Service - F5-TTS server with health endpoints and proxy."""

import asyncio
import logging
import signal
import sys
import time
import threading
import queue
import warnings
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import os

from server_manager import tts_server_manager

# Suppress known harmless warnings from F5-TTS dependencies
warnings.filterwarnings("ignore", message=".*torchaudio.load_with_torchcodec.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Trying to convert audio automatically.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*You have not specified a value for the `type` parameter.*", category=UserWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state
_startup_success = False
_request_counter = 0
_last_request_time = None
_last_health_log_time = 0


def monitor_f5_server_logs():
    """Monitor F5-TTS server activity and add timestamps to output."""
    global _request_counter, _last_request_time

    while True:
        try:
            if tts_server_manager.process and tts_server_manager.process.poll() is None:
                # Read output from F5-TTS server and add timestamps
                try:
                    line = tts_server_manager.process.stdout.readline()
                    if line:
                        line = line.strip()
                        if line:
                            # Add timestamp and format F5-TTS output
                            if line.startswith("gen_text"):
                                # Track generation activity and extract text
                                _request_counter += 1
                                _last_request_time = time.time()
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                                # Extract text content from gen_text line for correlation
                                try:
                                    # Format: "gen_text 0 [actual text]"
                                    parts = line.split(" ", 2)
                                    if len(parts) >= 3:
                                        text_content = parts[2][:50] + "..." if len(parts[2]) > 50 else parts[2]
                                        print(f"{timestamp} - F5-TTS - INFO - 🎵 [F5-GEN-{_request_counter:03d}] Synthesizing: {text_content}")
                                    else:
                                        print(f"{timestamp} - F5-TTS - INFO - 🎵 [F5-GEN-{_request_counter:03d}] {line}")
                                except:
                                    print(f"{timestamp} - F5-TTS - INFO - 🎵 [F5-GEN-{_request_counter:03d}] {line}")
                            elif "Starting app" in line or "Running on" in line:
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                                print(f"{timestamp} - F5-TTS - INFO - {line}")
                            elif line.startswith("INFO:"):
                                # Pass through uvicorn INFO logs with timestamp
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                                print(f"{timestamp} - F5-TTS - {line}")
                            elif line.startswith("ref_text"):
                                # Suppress ref_text output - it's just debug noise
                                pass
                            else:
                                # Other output (model loading, etc.)
                                print(line)
                    else:
                        time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error reading F5-TTS output: {e}")
                    time.sleep(1)
            else:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Error monitoring F5-TTS: {e}")
            time.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    global _startup_success

    # Startup
    logger.info("Starting TTS service...")

    try:
        # Start the F5-TTS server
        success = tts_server_manager.start_server()
        _startup_success = success

        if success:
            logger.info("✅ TTS service started successfully")
            logger.info("🎵 [TTS-SERVER] F5-TTS logs will appear directly below")

            # Start monitoring thread for F5-TTS server logs
            monitor_thread = threading.Thread(target=monitor_f5_server_logs, daemon=True)
            monitor_thread.start()
        else:
            logger.warning("⚠️ TTS server failed to start, but service will continue")

    except Exception as e:
        logger.error(f"❌ Error during startup: {e}")
        _startup_success = False

    yield

    # Shutdown
    logger.info("Shutting down TTS service...")
    try:
        tts_server_manager.cleanup()
        logger.info("✅ TTS service shutdown complete")
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Gaia TTS Service",
    description="F5-TTS server with health endpoints",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker and load balancers."""
    try:
        # Check if F5-TTS server is running
        is_valid, message = tts_server_manager.validate_connection()

        if is_valid:
            return {
                "status": "healthy",
                "message": message,
                "tts_server": "running",
                "port": tts_server_manager.port
            }
        else:
            # Return 503 if TTS server is not responding
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "message": message,
                    "tts_server": "not_responding",
                    "port": tts_server_manager.port
                }
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "message": f"Health check error: {str(e)}",
                "tts_server": "unknown"
            }
        )


@app.get("/")
async def root():
    """Root endpoint that provides service information."""
    return {
        "service": "Gaia TTS Service",
        "description": "F5-TTS server with health endpoints",
        "version": "1.0.0",
        "tts_server_url": tts_server_manager.server_url,
        "health_endpoint": "/health",
        "gradio_interface": f"http://localhost:{tts_server_manager.port}"
    }


@app.get("/status")
async def status():
    """Detailed status endpoint."""
    try:
        is_valid, message = tts_server_manager.validate_connection()

        return {
            "tts_server": {
                "running": tts_server_manager.is_running,
                "port": tts_server_manager.port,
                "url": tts_server_manager.server_url,
                "responding": is_valid,
                "message": message
            },
            "startup_success": _startup_success,
            "process_id": tts_server_manager.process.pid if tts_server_manager.process else None,
            "request_stats": {
                "total_requests": _request_counter,
                "last_request_time": _last_request_time,
                "time_since_last_request": time.time() - _last_request_time if _last_request_time else None
            }
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Status check error: {str(e)}")


@app.get("/activity")
async def activity():
    """Get TTS server activity information."""
    global _request_counter, _last_request_time

    return {
        "total_requests": _request_counter,
        "last_request_time": _last_request_time,
        "last_request_ago_seconds": time.time() - _last_request_time if _last_request_time else None,
        "server_active": tts_server_manager.is_running,
        "timestamp": time.time()
    }


def handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    tts_server_manager.cleanup()
    sys.exit(0)


def main():
    """Main entry point for the TTS service."""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Start the FastAPI server
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,  # Cloud Run provides $PORT
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
