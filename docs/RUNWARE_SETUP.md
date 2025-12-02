# Runware SDK Docker Setup Guide

This guide shows you how to set up Runware AI image generation in your Docker-based Gaia environment.

## 🚀 Quick Start

### 1. Get Your Runware API Key

1. Visit [Runware Dashboard](https://runware.ai/dashboard)
2. Sign up for an account
3. Navigate to API Keys section
4. Generate a new API key
5. Copy the API key (starts with `rw_`)

### 2. Configure Environment Variables

Add your API key to the secrets file:

```bash
# Copy the example file if you haven't already
cp secrets/secrets.env.example secrets/.secrets.env

# Edit the secrets file
nano secrets/.secrets.env
```

Add your Runware API key:
```bash
RUNWARE_API_KEY=rw_your_actual_api_key_here
```

### 3. Build Docker Images

Run the build script to rebuild your Docker images with Runware SDK:

```bash
cd backend
./scripts/build-with-runware.sh
```

Or build manually:
```bash
cd backend
docker compose build dev
docker compose build prod
docker compose build test
```

**Note**: The Runware SDK version is pinned to `0.4.25` (latest available on PyPI).

### 4. Start the Development Server

```bash
cd backend
docker compose up dev
```

### 5. Test the Integration

Check if Runware is working:

```bash
# Health check
curl http://localhost:8000/api/health/runware

# Test image generation
curl -X POST http://localhost:8000/api/images/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A majestic dragon in a fantasy landscape",
    "model": "runware:101@1",
    "size": "1024x1024",
    "style": "fantasy art"
  }'
```

## 🔧 Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RUNWARE_API_KEY` | Required | Your Runware API key |
| `RUNWARE_TIMEOUT` | 120 | Request timeout in seconds |
| `RUNWARE_MAX_RETRIES` | 3 | Maximum retry attempts |
| `RUNWARE_RETRY_DELAY` | 2.0 | Delay between retries |
| `RUNWARE_DEFAULT_MODEL` | runware:101@1 | Default model to use |
| `RUNWARE_MAX_CONCURRENT` | 5 | Max concurrent requests |

### Available Models

Runware provides access to multiple AI models:

- **runware:101@1** - Runware's own high-quality model
- **blackforestlabs:flux-dev@1** - FLUX development model
- **openai:dall-e-3@1** - OpenAI's DALL-E 3
- **ideogram:ideogram-v1@1** - Ideogram with text support
- **google:imagen-3@1** - Google's Imagen 3

## 🐳 Docker Commands

### Development
```bash
# Start development server with hot-reload
docker compose up dev

# View logs
docker compose logs -f dev

# Rebuild and restart
docker compose build dev && docker compose up dev
```

### Production
```bash
# Build and start production server
docker compose build prod
docker compose up prod

# Run in background
docker compose up -d prod
```

### Testing
```bash
# Run tests
docker compose up test

# Run specific tests
docker compose run test pytest tests/test_runware_integration.py
```

## 🔍 Troubleshooting

### Common Issues

1. **"Runware API key not configured"**
   - Check that `RUNWARE_API_KEY` is set in `secrets/.secrets.env`
   - Ensure the secrets file is being loaded by Docker Compose

2. **"Connection failed"**
   - Check your internet connection
   - Verify the API key is valid
   - Check Runware service status

3. **"Model not available"**
   - Try a different model ID
   - Check the available models endpoint: `GET /api/images/models`

4. **Docker build fails**
   - Ensure you have the latest `requirements.txt` with `runware>=1.0.0`
   - Check Docker has internet access to download packages
   - Try clearing Docker cache: `docker system prune -a`

### Debug Commands

```bash
# Check if Runware is installed in container
docker compose exec dev pip list | grep runware

# Check environment variables
docker compose exec dev env | grep RUNWARE

# View container logs
docker compose logs dev | grep -i runware

# Test connection manually
docker compose exec dev python -c "
import asyncio
from runware import Runware
async def test():
    r = Runware()
    await r.connect()
    print('Connected successfully!')
    await r.disconnect()
asyncio.run(test())
"
```

## 📊 Monitoring

### Health Checks

The system includes health checks for Runware:

- **Endpoint**: `GET /api/health/runware`
- **Response**: JSON with connection status and available models

### Usage Tracking

Monitor your Runware usage:

- Check the Runware dashboard for usage statistics
- Monitor logs for generation times and success rates
- Set up alerts for quota limits

## 🔄 Updates

To update the Runware SDK:

1. Update `requirements.txt` with new version
2. Rebuild Docker images: `./scripts/build-with-runware.sh`
3. Restart containers: `docker compose restart`

## 🆘 Support

- **Runware Documentation**: https://runware.ai/docs
- **Runware Discord**: https://discord.gg/runware
- **GitHub Issues**: Create an issue in the Gaia repository

## 📝 Notes

- The Runware SDK uses WebSocket connections for better performance
- Images are cached locally in `/home/gaia/images` (Docker volume)
- The service automatically falls back to Flux/Gemini if Runware is unavailable
- All API calls are logged for debugging and monitoring
