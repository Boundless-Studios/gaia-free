# Simple Cloud Run Dockerfile without BuildKit requirements
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 gaia && \
    useradd --uid 1000 --gid 1000 --create-home --shell /bin/bash gaia

USER gaia
WORKDIR /home/gaia

# Install Python dependencies
COPY --chown=gaia:gaia requirements.txt ./requirements.txt
RUN pip install --user --no-cache-dir -r requirements.txt

# Set environment
ENV PATH=/home/gaia/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/home/gaia:/home/gaia/src

# Copy application code
COPY --chown=gaia:gaia src/ ./src/
COPY --chown=gaia:gaia scripts/ ./scripts/

# Expose Cloud Run port
EXPOSE 8080

# Use Cloud Run entrypoint
ENTRYPOINT ["python", "/home/gaia/backend/scripts/entrypoint_cloud_run.py"]
