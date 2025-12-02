# System Requirements for Gaia

## Required System Dependencies

Gaia requires the following system-level dependencies to function properly:

### 1. **FFmpeg** (Required for voice detection and audio processing)
- **Purpose**: Decodes audio for voice activity detection during transcription
- **Auto-install**: ✅ Yes (on macOS and Linux)
- **Manual install**:
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - RedHat/CentOS: `sudo yum install ffmpeg`
  - Arch Linux: `sudo pacman -S ffmpeg`
  - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)

### 3. **Node.js/npm** (Required for frontend)
- **Purpose**: Builds and runs the React frontend
- **Auto-install**: ❌ No (requires manual installation)
- **Manual install**: Download from [nodejs.org](https://nodejs.org/)

## Python Dependencies

All Python dependencies are automatically installed via `requirements.txt` when you run `gaia_launcher.py`.

## Automatic Installation

When you run `python3 gaia_launcher.py`, the launcher will:

1. Check for missing system dependencies
2. Attempt to install them automatically using:
   - **macOS**: Homebrew (`brew`)
   - **Linux**: Package manager (`apt-get`, `yum`, etc.)
3. Fall back to manual installation instructions if automatic installation fails

## Platform-Specific Notes

### macOS
- Requires [Homebrew](https://brew.sh/) for automatic dependency installation
- If Homebrew is not installed, you'll be prompted to install it

### Linux
- Requires `sudo` privileges for automatic installation
- Supports Debian/Ubuntu (apt), RedHat/CentOS (yum), and Arch (pacman)

### Windows
- Automatic installation not supported
- Manual installation required for system dependencies
- WSL (Windows Subsystem for Linux) recommended for better compatibility

### Docker/Container Environments
- All system dependencies should be included in the container image
- See `Dockerfile` for container setup

## Verification

To verify all dependencies are installed correctly:

```bash
# Check FFmpeg
ffmpeg -version

# Check Node.js/npm
node --version
npm --version
```

## Troubleshooting

If automatic installation fails:

1. **Permission Issues**: Make sure you have appropriate permissions (sudo on Linux/macOS)
2. **Package Manager Issues**: Update your package manager first:
   - macOS: `brew update`
   - Ubuntu/Debian: `sudo apt-get update`
   - RedHat/CentOS: `sudo yum update`
3. **Network Issues**: Ensure you have internet connectivity for downloading packages
4. **Manual Installation**: Follow the manual installation instructions above

## Optional Dependencies

These enhance functionality but are not required:

- **Ollama**: For local LLM inference (auto-detected if available)
- **CUDA**: For GPU acceleration with local models
- **Docker**: For containerized deployment