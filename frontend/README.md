# Gaia Frontend

A modern React application for the Gaia D&D game system, built with Vite and designed for Docker deployment.

## Quick Start with Docker

### Development
```bash
# Start development server
docker-compose --profile dev up

# Or manually
docker build -f Dockerfile.dev -t gaia-frontend-dev .
docker run -p 3000:3000 -v $(pwd):/app gaia-frontend-dev
```

### Production
```bash
# Build and run production version
docker-compose --profile prod up

# Or manually
docker build -t gaia-frontend .
docker run -p 3000:3000 gaia-frontend
```

### Testing
```bash
# Run all tests in Docker
docker-compose --profile test up

# Or manually
docker build -f Dockerfile.test -t gaia-frontend-test .
docker run --rm gaia-frontend-test
```

## Project Structure

```
frontend-app/
├── src/
│   ├── components/           # React components
│   │   ├── audio/           # Audio-related components
│   │   ├── game/            # Game-specific components
│   │   ├── ui/              # General UI components
│   │   ├── common/          # Shared components
│   │   └── layout/          # Layout components
│   ├── pages/               # Page components
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API and external services
│   ├── stores/              # State management
│   ├── utils/               # Utility functions
│   ├── types/               # TypeScript type definitions
│   ├── config/              # Configuration files
│   ├── assets/              # Static assets
│   └── styles/              # CSS and styling
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   ├── e2e/                 # End-to-end tests
│   ├── __mocks__/           # Test mocks
│   └── fixtures/            # Test data
├── public/                  # Public assets
├── docs/                    # Documentation
└── scripts/                 # Build and utility scripts
```

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build |
| `npm run test` | Run unit tests in watch mode |
| `npm run test:run` | Run unit tests once |
| `npm run test:coverage` | Run tests with coverage |
| `npm run test:e2e` | Run end-to-end tests |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Fix ESLint errors |
| `npm run format` | Format code with Prettier |
| `npm run type-check` | Run TypeScript type checking |

## Docker Commands

| Command | Description |
|---------|-------------|
| `npm run docker:build` | Build production Docker image |
| `npm run docker:run` | Run production Docker container |
| `npm run docker:test` | Build and run tests in Docker |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_BACKEND_URL` | Backend API URL | `http://localhost:8000` |
| `VITE_IS_WSL` | Running in WSL environment | `false` |
| `VITE_AUTH0_DOMAIN` | Auth0 domain for authentication | - |
| `VITE_AUTH0_CLIENT_ID` | Auth0 client ID | - |
| `VITE_AUTH0_AUDIENCE` | Auth0 API audience | - |
| `VITE_ENABLE_VOICE_INPUT` | Enable voice input feature | `true` |
| `VITE_ENABLE_CONVERSATIONAL_MODE` | Enable conversational mode | `true` |

See `.env.example` for a complete template.

## Voice Input Configuration

This application uses **ElevenLabs Scribe V2 Realtime** for speech-to-text transcription with ultra-low latency (150ms), proxied through the backend STT service for security.

### Architecture

Voice transcription follows a secure proxy pattern:
```
Frontend → Backend STT Service → ElevenLabs Scribe V2 API
```

The ElevenLabs API key is stored securely on the backend and never exposed to the frontend. This prevents API key leakage through browser inspection or network monitoring.

### Setup

1. **Backend Configuration** (handled by deployment):
   - ElevenLabs API key is configured in backend environment
   - STT service must be running (`speech-to-text` container)
   - WebSocket endpoint available at `/stt/transcribe/realtime`

2. **Frontend Configuration**:
   ```bash
   # Copy the example environment file
   cp .env.example .env

   # Ensure backend URL is configured (default works for local dev)
   VITE_API_BASE_URL=http://localhost:8000
   ```

3. **Enable Microphone Permissions**:
   - The browser will prompt for microphone access on first use
   - Grant permission to enable voice input

### Features

- **🗣️ Conversational Mode**: Natural conversation flow with automatic pause detection
- **🎤 Voice Activity Detection (VAD)**: Built-in VAD automatically detects when you stop speaking
- **⚡ Ultra-Low Latency**: 150ms transcription latency using Scribe V2
- **🌍 Multilingual**: Supports 92+ languages
- **📝 Real-Time Transcription**: See partial transcripts as you speak
- **🔄 Auto-Submit**: Automatically sends your message when you pause
- **🔒 Secure**: API key never exposed to frontend

### Usage

1. Click the microphone button (🎤) in the player view
2. Grant microphone permissions if prompted
3. Start speaking naturally
4. The system automatically detects pauses and transcribes
5. In conversational mode, messages are auto-sent after natural pauses
6. Click "Stop Listening" (🛑) to end the session

### Technical Details

- **Backend Proxy Architecture**: Frontend connects to backend WebSocket which proxies to ElevenLabs
- **Audio Format**: WebM/Opus encoded, resampled to PCM 16kHz by backend
- **Chunk Size**: 100ms for low latency
- **VAD Threshold**: 0.5 (configurable on backend)
- **Model**: ScribeRealtime V2
- **Authentication**: WebSocket requires Auth0 authentication

### Troubleshooting

**"Connection error with speech recognition service"**
- Ensure backend STT service is running: `docker ps | grep speech-to-text`
- Check backend logs: `docker logs gaia-stt-dev`
- Verify `VITE_API_BASE_URL` is correctly configured

**"Microphone access denied"**
- Check browser permissions (Settings → Privacy → Microphone)
- Try using HTTPS (required for some browsers)

**No transcription appearing**
- Check browser console for WebSocket connection errors
- Verify backend has valid ElevenLabs API key configured
- Check backend logs for transcription errors
- Ensure speaking loud enough for voice detection

## Testing

The project includes comprehensive testing:

- **Unit Tests**: Using Vitest and React Testing Library
- **Integration Tests**: API and component integration
- **E2E Tests**: Using Playwright for full user flows
- **Coverage**: Automated test coverage reporting

## Development

This frontend is designed to work independently and can be deployed as a standalone application. It communicates with the Gaia backend via REST API and WebSocket connections.

### Key Features

- Modern React 19 with hooks
- Vite for fast development and building
- Tailwind CSS for styling
- WebSocket support for real-time communication
- Protobuf support for efficient data serialization
- Audio recording and playback capabilities
- Responsive design for desktop and mobile

## Deployment

The application is containerized and ready for deployment to any Docker-compatible environment:

- Development containers with hot reload
- Production-optimized builds with multi-stage Docker
- Comprehensive test suite that runs in containers
- Health checks and proper security practices