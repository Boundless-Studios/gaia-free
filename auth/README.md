# Gaia Authentication Service

Shared authentication library for all Gaia services.

## Features

- JWT token creation and validation
- FastAPI middleware for authentication
- WebSocket authentication support
- Shared JWT_SECRET_KEY across services

## Installation

### As a Git Submodule

```bash
# Add to your project
git submodule add https://github.com/yourusername/gaia-auth.git auth

# Install dependencies
pip install -r auth/requirements.txt
```

### As a Python Package

```bash
pip install -e ./auth
```

## Configuration

Set these environment variables:

```bash
# Required
JWT_SECRET_KEY=your-secret-key-here

# Optional
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
DISABLE_AUTH=false  # Set to true for development
```

## Usage

### FastAPI Endpoints

```python
from gaia_auth import required_auth, optional_auth
from fastapi import FastAPI, Depends

app = FastAPI()

# Protected endpoint - requires authentication
@app.get("/protected")
async def protected_route(user=Depends(required_auth)):
    return {"user": user}

# Optional auth - works with or without token
@app.get("/public")
async def public_route(user=Depends(optional_auth)):
    if user:
        return {"message": f"Hello {user['sub']}"}
    return {"message": "Hello anonymous"}
```

### WebSocket Authentication

```python
from gaia_auth import verify_websocket_token

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Get token from query params or headers
    token = websocket.query_params.get("token")
    
    # Verify token
    user = await verify_websocket_token(websocket, token)
    if not user:
        return  # Connection already closed with error
    
    # Continue with authenticated user
    await handle_websocket(websocket, user)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Building Docker Image

```bash
docker build -t gaia-auth .
```

## License

MIT