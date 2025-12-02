FROM python:3.11-slim
ARG ARCH=amd64
ARG SOPS_VERSION=3.9.3

WORKDIR /app

# Install minimal system dependencies
# ffmpeg is needed for WebM audio decoding
# SOPS is needed for secrets decryption
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install SOPS for secrets decryption
RUN \
    curl -LO "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${ARCH}" && \
    mv "sops-v${SOPS_VERSION}.linux.${ARCH}" /usr/local/bin/sops && \
    chmod +x /usr/local/bin/sops

# Copy requirements and install (build context is repo root)
COPY speech-to-text/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and shared modules
COPY speech-to-text/src/ /app/src/
COPY auth/ /app/auth/
COPY db/ /app/db/
COPY speech-to-text/.settings.docker.env /app/.env

# Copy entrypoint script
COPY speech-to-text/scripts/docker-entrypoint-with-secrets.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Create directories
ENV AUDIO_STORAGE_PATH=/app/audio_storage
RUN mkdir -p ${AUDIO_STORAGE_PATH}/transcriptions

# Expose default port; Cloud Run will set $PORT
EXPOSE 8001

# Use entrypoint script for SOPS decryption
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the application; respect Cloud Run $PORT if provided
CMD ["sh", "-c", "python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8001} --access-log --log-level warning"]
