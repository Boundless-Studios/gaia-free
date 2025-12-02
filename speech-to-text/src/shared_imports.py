"""
Shared imports setup for speech-to-text service.
Sets up path to import from gaia-auth and gaia-db repositories.
"""

import sys
import os
from pathlib import Path

# Get the speech-to-text root directory
STT_ROOT = Path(__file__).parent.parent

# In Docker, modules are mounted at /app/auth and /app/db
# In local development, they're in the parent directory
if os.path.exists("/app/auth"):
    # Docker environment
    AUTH_PATH = Path("/app/auth")
    DB_PATH = Path("/app/db")
else:
    # Local development
    GAIA_ROOT = STT_ROOT.parent
    AUTH_PATH = GAIA_ROOT / "auth"
    DB_PATH = GAIA_ROOT / "db"

# Add paths to sys.path if they exist
if AUTH_PATH.exists():
    sys.path.insert(0, str(AUTH_PATH))
    
if DB_PATH.exists():
    sys.path.insert(0, str(DB_PATH))

# Log the setup
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Set up shared imports - Auth: {AUTH_PATH}, DB: {DB_PATH}")