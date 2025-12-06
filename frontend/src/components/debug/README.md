# Audio Debug Page

An admin page for diagnosing audio playback issues and viewing request history.

## Access

**Route**: `/admin/debug-audio`

Available in development and production (admin access required).

## Features

### 1. Recent Requests Table
- Displays last 50 audio playback requests
- Filterable by campaign ID
- Shows status, chunk counts, text preview, and timestamp
- Highlights requests with sequence issues (red left border)
- Auto-refreshes on page load

### 2. Diagnosis Panel
Click "Diagnose" on any request to see:
- **Request Info**: Status, campaign ID, total chunks, playback group, full text
- **Sequence Analysis**: Expected vs actual chunks, missing/extra sequences
- **Recommendations**: Actionable suggestions for fixing issues
- **Chunks Table**: Detailed list of all chunks with sequence numbers, status, artifact IDs

### 3. Status Indicators
- Status badges: completed (green), generated (blue), generating (yellow), pending (gray), failed (red)
- Sequence issues warning icon when chunks are missing or out of order

## Backend Endpoints

The debug page uses:

```
GET /api/debug/recent-audio-requests?limit=50&campaign_id=optional
GET /api/debug/diagnose-audio/{request_id}
```

## Troubleshooting

### Common Issues Diagnosed

1. **Missing Chunks**: Some chunks failed to generate (TTS errors)
   - Check ElevenLabs API status
   - Review backend logs for TTS failures

2. **Sequence Gaps**: Chunks stored with non-sequential numbers
   - Usually caused by concurrent TTS failures
   - Backend logs warning when gaps occur

3. **Zero Chunks**: Request created but no audio generated
   - Empty text or TTS service unavailable
   - Request will be marked as failed by cleanup

### Checking Backend Logs

```bash
docker logs -f gaia-backend-dev | grep AUDIO_DEBUG
```

## Development Notes

### File Structure
```
frontend/src/components/debug/
├── AudioDebugPage.jsx       # Main component (Tailwind CSS)
└── README.md                 # This file

backend/src/gaia/api/routes/
└── debug.py                  # Backend endpoints

backend/src/gaia/infra/audio/
├── audio_playback_service.py # diagnose_playback_request, get_recent_requests
└── playback_request_writer.py # Chunk persistence logic
```

### Styling
Uses Tailwind CSS (light theme) matching other admin pages like `/admin/prompts`.
