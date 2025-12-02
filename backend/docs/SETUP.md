# Gaia D&D Campaign Manager - Setup Guide

## Quick Start

### Windows
Double-click `start_gaia.bat` or run in Command Prompt:
```batch
start_gaia.bat
```

### Linux/macOS/WSL
```bash
bash start_gaia.sh
```

### Direct Python (all platforms)
```bash
python setup.py
```

## Stopping Gaia

### Linux/macOS/WSL
```bash
bash stop_gaia.sh
```

### Manual Stop
Press `Ctrl+C` in the terminal where Gaia is running.

## What These Scripts Do

### Start Scripts
1. **Dependency Check**: Verifies Python 3.7+ and Node.js are installed
2. **Python Dependencies**: Installs required packages from `requirements.txt`
3. **Process Cleanup**: Kills any existing Gaia processes
4. **Auto-reload Setup**: Configures backend and frontend with hot-reload
5. **Server Launch**: Starts both backend (port 8000) and frontend (port 3000)
6. **Browser Opening**: Automatically opens http://localhost:3000

## Client-Side Audio Playback

Narration audio is enabled by default. Use the optional kill switch only when you need to suppress every audio side effect:

- Export `GAIA_AUDIO_DISABLED=true` before starting the backend to turn off auto-TTS and client audio generation. Dropping the variable (or setting it to false) keeps the feature active.
- Configure a storage bucket with `CLIENT_AUDIO_BUCKET` (or reuse `CAMPAIGN_MEDIA_BUCKET`). Optional overrides include `CLIENT_AUDIO_BASE_PATH` (defaults to `media/audio`) and `CLIENT_AUDIO_URL_TTL_SECONDS` for the signed URL TTL (default 900s).
- Without a bucket the backend serves audio through `GET /api/media/audio/{session_id}/{filename}` using the local artifact cache.
- Clean up stale assets by scheduling `python scripts/prune_audio_artifacts.py --max-age-hours 24`.
- The mute toggle persists in `localStorage` (`gaiaAudioMuted`) so QA can disable sound across reloads.

Validate on staging first—`/api/chat` responses will include `message.structured_data.audio` when the pipeline is active.

### Stop Scripts
1. **PID File Cleanup**: Terminates processes using saved process IDs
2. **Process Search**: Finds and kills remaining Gaia processes
3. **Port Cleanup**: Frees up ports 3000 and 8000

## Features

### Auto-reload
- **Backend**: Watches Python files in `src/` directory
- **Frontend**: Watches React files in `frontend-vite/` directory
- **Hot Reload**: Changes are automatically applied without restart

### Cross-platform Process Management
- **Windows**: Uses process groups for clean termination
- **Unix/Linux**: Uses session IDs for proper cleanup
- **Robust Cleanup**: Handles zombie processes and port conflicts

### Error Handling
- **Dependency Installation**: Tries multiple installation methods
- **Process Recovery**: Automatically restarts failed processes
- **Graceful Shutdown**: Proper cleanup on exit

## Troubleshooting

### Python Issues
If you get "externally-managed-environment" errors:
1. Scripts automatically try `--break-system-packages` flag
2. Or create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   python setup.py
   ```

### Port Issues
If ports 3000 or 8000 are busy:
1. Run the stop script first
2. Or manually kill processes:
   ```bash
   # Linux/macOS
   lsof -ti:3000 | xargs kill -9
   lsof -ti:8000 | xargs kill -9
   
   # Windows
   netstat -ano | findstr :3000
   taskkill /F /PID <PID>
   ```

### Node.js Issues
If npm/Node.js is not found:
1. Install Node.js from https://nodejs.org/
2. Make sure "Add to PATH" is checked during installation
3. Restart your terminal

## File Structure

```
Gaia/
├── setup.py              # Main setup script
├── start_gaia.sh         # Linux/macOS start script
├── start_gaia.bat        # Windows start script
├── stop_gaia.sh          # Linux/macOS stop script
├── requirements.txt      # Python dependencies
├── gaia.pid              # Process IDs (auto-generated)
├── src/                  # Backend source code
│   └── gaia/
│       └── api/
│           └── main.py   # FastAPI backend
└── frontend-vite/        # React frontend (Vite)
    ├── src/
    │   └── App.jsx
    └── package.json
```

## URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Dependencies

### Python
- fastapi
- uvicorn
- pydantic
- openai
- openai-agents
- requests
- psutil
- python-multipart

### Node.js
- react
- react-dom
- @rsbuild/core
- @rsbuild/plugin-react
