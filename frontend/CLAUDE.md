# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

```bash
# One-click setup
python3 gaia_launcher.py

# Backend server
cd src && python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend development
cd src/frontend && npm run dev

# Check system health
curl http://localhost:8000/api/health
```

## Architecture Overview


**Frontend Usage:**
1. Click "🎙️ Show Transcription" button
2. Click "🎤 Start Listening" to begin
3. Voice activity indicator shows green when speaking
4. Click "📤 Send Unsent Text" to send to chat

### Core
- `GET /api/health` - System health check
- `POST /api/chat` - Send chat message
- `WebSocket /api/chat/stream` - Streaming chat

### Audio
- `WebSocket /ws/transcribe/continuous` - Continuous transcription
- `GET /api/voice-activity/{session_id}` - Voice activity status
- `POST /api/tts/synthesize` - Generate speech
- `GET /api/tts/auto/status` - Auto-TTS status

### Campaign
- `GET /api/campaigns` - List campaigns
- `POST /api/campaigns/new` - Create campaign
- `GET /api/campaigns/{id}/history` - Get history

### Images
- `POST /api/images/generate` - Generate image
- `GET /api/images/models` - Available models
