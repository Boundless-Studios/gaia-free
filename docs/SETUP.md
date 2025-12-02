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

Gaia now ships browser narration audio on by default. The only runtime toggle is an escape hatch for unusual environments:

- **Disable globally** by exporting `GAIA_AUDIO_DISABLED=true` before starting the backend. Omitting the variable keeps client audio, auto-TTS, and seamless playback enabled.
- **Bucket configuration**: set `CLIENT_AUDIO_BUCKET` (or `CAMPAIGN_MEDIA_BUCKET`) to the Google Cloud Storage bucket used for per-session artifacts. Optional overrides include `CLIENT_AUDIO_BASE_PATH` (defaults to `media/audio`) and `CLIENT_AUDIO_URL_TTL_SECONDS` for signed-URL lifetimes.
- **Local development**: when no bucket is configured, audio files are served through the fallback proxy endpoint `GET /api/media/audio/{session_id}/{filename}`.
- **Housekeeping**: run `python scripts/prune_audio_artifacts.py --max-age-hours 24` on a schedule to remove stale artifacts from disk and GCS.
- **Mute persistence**: browsers persist the mute toggle via `localStorage` (`gaiaAudioMuted`) so QA can keep audio silent across reloads.

During rollouts, verify `/api/chat` responses contain an `audio` object in `message.structured_data` before shipping to production.

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
