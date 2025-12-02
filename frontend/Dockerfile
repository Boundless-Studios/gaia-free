# Multi-stage build for optimized production deployment
FROM node:22-alpine AS builder

WORKDIR /app

# Upgrade npm to latest version
RUN npm install -g npm@latest

# Copy package files (build context is repo root)
COPY frontend/package.json frontend/package-lock.json ./

# Install all dependencies for building
RUN npm ci --legacy-peer-deps

# Copy source code from frontend directory
COPY frontend/ .

# Accept Auth0 build arguments and set as environment variables for Vite build
# Default values are provided so build works without docker-compose passing them
ARG VITE_AUTH0_DOMAIN=your-tenant.us.auth0.com
ARG VITE_AUTH0_CLIENT_ID=your-auth0-client-id
ARG VITE_AUTH0_AUDIENCE=https://api.your-domain.com
ARG VITE_AUTH0_REDIRECT_URI
ARG VITE_AUTH0_LOGOUT_URL

ENV VITE_AUTH0_DOMAIN=$VITE_AUTH0_DOMAIN
ENV VITE_AUTH0_CLIENT_ID=$VITE_AUTH0_CLIENT_ID
ENV VITE_AUTH0_AUDIENCE=$VITE_AUTH0_AUDIENCE
ENV VITE_AUTH0_REDIRECT_URI=$VITE_AUTH0_REDIRECT_URI
ENV VITE_AUTH0_LOGOUT_URL=$VITE_AUTH0_LOGOUT_URL

# Build the application
ENV NODE_ENV=production
RUN npm run build

# Production image using nginx
FROM nginx:alpine AS runner

# Install curl and envsubst for health checks and templating
RUN apk add --no-cache curl gettext

# Copy built application
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configurations
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf.template
COPY frontend/nginx-main.conf /etc/nginx/nginx.conf
COPY frontend/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/ || exit 1

# Start nginx with templated configuration
CMD ["/docker-entrypoint.sh"]
