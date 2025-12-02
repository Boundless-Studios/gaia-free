# TTS Service Dockerfile - F5-TTS server

ARG PYTHON_VERSION=3.11

# Build stage for dependencies
FROM python:${PYTHON_VERSION}-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /build
COPY tts-service/requirements.txt .
RUN pip install --user -r requirements.txt

# Runtime stage
FROM python:${PYTHON_VERSION}-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with consistent UID
ARG USER_UID=1000
ARG USER_GID=1000
RUN groupadd --gid ${USER_GID} gaia && \
    useradd --uid ${USER_UID} --gid ${USER_GID} --create-home --shell /bin/bash gaia

USER gaia
WORKDIR /home/gaia

# Copy Python packages from builder
COPY --from=builder --chown=gaia:gaia /root/.local /home/gaia/.local
ENV PATH=/home/gaia/.local/bin:$PATH

# Set environment variables
ENV PYTHONPATH=/home/gaia:/home/gaia/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create necessary directories
RUN mkdir -p logs tmp .cache/huggingface/hub

# Copy application code
COPY --chown=gaia:gaia tts-service/src/ ./src/
COPY --chown=gaia:gaia tts-service/entrypoint.sh /home/gaia/entrypoint.sh

# Make entrypoint executable
RUN chmod +x /home/gaia/entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:7860/health || exit 1

EXPOSE 7860

# Use entrypoint for startup
ENTRYPOINT ["/home/gaia/entrypoint.sh"]
