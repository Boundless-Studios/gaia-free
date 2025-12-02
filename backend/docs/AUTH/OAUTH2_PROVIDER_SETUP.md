# OAuth2 Provider Setup Guide

## Why Providers Aren't Configured

OAuth2 providers (Google, GitHub, Discord) require you to register your application with each provider and obtain client credentials. These are not configured by default because:

1. **Security**: Client IDs and secrets are unique to your application
2. **Domain Specific**: Callback URLs must match your domain
3. **Manual Process**: Each provider requires manual registration

## Quick Setup for Testing

### Option 1: Use the CLI Test Script (No OAuth2 Required)

Test the authentication system without OAuth2 providers:

```bash
cd backend
python3 scripts/auth/test_auth_cli.py
```

This script:
- Creates test users directly in the database
- Generates JWT tokens
- Tests all auth endpoints
- Provides curl commands for manual testing

### Option 2: Configure Google OAuth2

#### Step 1: Create Google OAuth2 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API:
   - Go to "APIs & Services" > "Library"
   - Search for "Google+ API"
   - Click "Enable"
4. Create OAuth2 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Web application"
   - Add authorized redirect URIs:
     - `http://localhost:8000/api/auth/callback/google` (for development)
     - `http://localhost:5173/auth/callback` (for frontend)
5. Copy the Client ID and Client Secret

#### Step 2: Add to Configuration

Add to `.settings.docker.env`:
```env
# Google OAuth2
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

Add to `secrets/.secrets.env`:
```env
# Google OAuth2
GOOGLE_CLIENT_SECRET=your-client-secret
```

#### Step 3: Restart Backend

```bash
docker compose restart backend-dev
```

#### Step 4: Verify Configuration

```bash
curl http://localhost:8000/api/auth/providers
```

Should return:
```json
[
  {
    "name": "google",
    "display_name": "Google"
  }
]
```

### Option 3: Configure GitHub OAuth2

#### Step 1: Create GitHub OAuth App

1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Click "New OAuth App"
3. Fill in:
   - Application name: "Gaia Development"
   - Homepage URL: `http://localhost:5173`
   - Authorization callback URL: `http://localhost:8000/api/auth/callback/github`
4. Click "Register application"
5. Copy Client ID and generate a Client Secret

#### Step 2: Add to Configuration

Add to `.settings.docker.env`:
```env
GITHUB_CLIENT_ID=your-github-client-id
```

Add to `secrets/.secrets.env`:
```env
GITHUB_CLIENT_SECRET=your-github-client-secret
```

### Option 4: Configure Discord OAuth2

#### Step 1: Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Name it "Gaia Development"
4. Go to OAuth2 > General
5. Add redirect URL: `http://localhost:8000/api/auth/callback/discord`
6. Copy Client ID and Client Secret

#### Step 2: Add to Configuration

Add to `.settings.docker.env`:
```env
DISCORD_CLIENT_ID=your-discord-client-id
```

Add to `secrets/.secrets.env`:
```env
DISCORD_CLIENT_SECRET=your-discord-client-secret
```

## Testing the OAuth2 Flow

### Via Command Line

```bash
# 1. Check providers
curl http://localhost:8000/api/auth/providers

# 2. Get login URL (replace 'google' with your provider)
curl -v http://localhost:8000/api/auth/login/google

# 3. Follow the redirect URL in a browser
# 4. After authentication, you'll be redirected back with tokens
```

### Via Frontend

1. Start frontend: `cd frontend && npm run dev`
2. Navigate to `http://localhost:5173`
3. Click on login button for your configured provider
4. Complete authentication
5. You'll be redirected back to the app, logged in

## Environment Variables Reference

### Required for OAuth2

In `.settings.docker.env`:
```env
# Frontend URL for redirects
FRONTEND_URL=http://localhost:5173

# OAuth2 Client IDs (public)
GOOGLE_CLIENT_ID=
GITHUB_CLIENT_ID=
DISCORD_CLIENT_ID=
```

In `secrets/.secrets.env`:
```env
# OAuth2 Client Secrets (private)
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_SECRET=
DISCORD_CLIENT_SECRET=

# JWT Secret (generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-256-bit-secret-key

# Database
DATABASE_URL=postgresql://gaia:password@postgres:5432/gaia
```

## Troubleshooting

### "No providers configured"
- Check that client ID and secret are both set
- Verify environment variables are loaded (check Docker logs)
- Restart the backend after adding credentials

### "Provider not configured" error
- Make sure the provider name matches exactly: `google`, `github`, or `discord`
- Check that both CLIENT_ID and CLIENT_SECRET are set for that provider

### Database connection issues
- Ensure PostgreSQL is running: `docker compose --profile dev up postgres`
- Check DATABASE_URL in secrets.env matches your PostgreSQL credentials

### JWT errors
- Generate a proper JWT_SECRET_KEY: `openssl rand -hex 32`
- Add it to secrets/.secrets.env
- Restart the backend

## Security Notes

1. **Never commit secrets**: The `secrets.env` file should never be committed to git
2. **Use HTTPS in production**: OAuth2 requires HTTPS for production deployments
3. **Rotate secrets regularly**: Change JWT_SECRET_KEY periodically
4. **Limit redirect URIs**: Only add the specific URLs you need

## Next Steps

After configuring at least one provider:

1. Test the authentication flow
2. Verify tokens are being generated
3. Test protected endpoints with tokens
4. Check admin role enforcement
5. Proceed with adding authentication to main API endpoints