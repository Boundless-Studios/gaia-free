"""
Setup imports for shared modules (auth and db).
Import this at the top of any file that needs auth or db imports.
"""

import sys
from pathlib import Path

# Get the project root directory (where auth and db submodules live)
# Starting from: /home/lya/code/gaia/backend/src/shared_imports.py
# Going up to: /home/lya/code/gaia/
BACKEND_SRC = Path(__file__).parent  # /home/lya/code/gaia/backend/src
BACKEND_ROOT = BACKEND_SRC.parent    # /home/lya/code/gaia/backend
PROJECT_ROOT = BACKEND_ROOT.parent   # /home/lya/code/gaia

# Add project root to Python path so we can import auth and db modules
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Now auth and db modules can be imported directly
# Example: from auth.src.middleware import CurrentUser
# Example: from db.src import get_async_db