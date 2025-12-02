#!/usr/bin/env python3
"""
Uvicorn runner script for Gaia FastAPI application.
This script ensures proper environment setup and starts the FastAPI server.
"""

import os
import sys
import uvicorn
from pathlib import Path

def main():
    """Start the FastAPI application with uvicorn."""
    
    print("Starting uvicorn runner...")
    
    # Add the gaia root, project root and src directory to Python path
    backend_root = Path(__file__).parent  # /home/lya/code/gaia/backend
    gaia_root = backend_root.parent       # /home/lya/code/gaia (where auth submodule is)
    src_dir = backend_root / "src"        # /home/lya/code/gaia/backend/src
    
    print(f"Gaia root: {gaia_root}")
    print(f"Backend root: {backend_root}")
    print(f"Source directory: {src_dir}")
    
    # Add gaia root first so auth and db submodules can be found
    if str(gaia_root) not in sys.path:
        sys.path.insert(0, str(gaia_root))
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    
    print(f"Python path: {sys.path}")
    
    # Import the FastAPI app
    try:
        print("Importing FastAPI app...")
        from gaia.api.app import app
        print("FastAPI app imported successfully")
    except ImportError as e:
        print(f"Error importing FastAPI app: {e}")
        print(f"Python path: {sys.path}")
        sys.exit(1)
    
    print("Starting uvicorn server...")
    
    # Start uvicorn server using import string for reload support
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "gaia.api.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=[str(src_dir)],
        reload_includes=["*.py"],
        log_level="info"
    )

if __name__ == "__main__":
    main()
