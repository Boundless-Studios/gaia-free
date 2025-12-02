#!/bin/bash
set -e

echo "=== Gaia TTS Service Starting ==="
echo "Environment: $(whoami)@$(hostname)"
echo "Working directory: $(pwd)"

# Check Python and pip
echo "Python version: $(python3 --version)"
echo "Pip version: $(pip --version)"

# Check F5-TTS installation
echo "Checking F5-TTS installation..."
if command -v f5-tts_infer-gradio >/dev/null 2>&1; then
    echo "✅ f5-tts_infer-gradio found"
else
    echo "❌ f5-tts_infer-gradio not found"
    echo "Available F5-TTS commands:"
    find /home/gaia/.local/bin -name "*f5*" -o -name "*tts*" || echo "None found"
fi

# Create necessary directories
mkdir -p logs tmp

# Set Python path
export PYTHONPATH="/home/gaia:/home/gaia/src:$PYTHONPATH"

echo "=== Starting TTS Service ==="
echo "PYTHONPATH: $PYTHONPATH"

# Start the TTS service
cd /home/gaia/src
exec python3 main.py