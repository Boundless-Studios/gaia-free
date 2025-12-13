# Gaia - AI-Powered D&D Campaign Manager

An intelligent Dungeon Master powered by AI that manages D&D campaigns with automatic agent handoffs for different
aspects of gameplay.

## 📋 Prerequisites

Make sure the following tools are installed:

1. **Python 3.8+** - [Download here](https://python.org/)
2. **Node.js 16+** - [Download here](https://nodejs.org/)
4. **Docker**      - [Download here](https://docs.docker.com/desktop/)
5. **Age**         - [Download here](https://github.com/FiloSottile/age)
6. **uv**          - [Download here](https://github.com/astral-sh/uv/)
6. **sops**        - [Download here](https://github.com/getsops/sops) 
7. **make** — typically preinstalled on macOS/Linux; Windows users should install via WSL or MinGW.

You can verify all prerequisites with:

```shell
make prerequisites
```

## 🔐 Project Initialization

Before starting the services for the first time, initialize the project:

```shell
make init
```

This command will:

* Generate a new Age private key for the project (if one does not already exist).
* Run uv sync to create/sync the Python virtual environment and install all required dependencies.

Keep the generated private key safe. Do not commit it to version control.

## 🚀 Start the services

Start all required containers:

```shell
make start
```

## 🛑 Stop the services

Stop the running containers:

```shell
make stop
```

## 🧹 Clean up

Remove all temporary artifacts generated during execution:

```shell
make clean
```

## Configure SOPS

This guide explains how to set up SOPS (Secrets OPerationS) for managing encrypted secrets in the Gaia project.

### Overview

We use SOPS with age encryption to:
- Encrypt sensitive configuration files before committing to git
- Allow multiple team members to decrypt secrets using their own age keys
- Sync secrets to Google Cloud Secret Manager for production deployments

### Quick Start for New Team Members

#### 1. Install age and SOPS

**On Linux/WSL:**
bash
Install age
sudo apt-get update
sudo apt-get install age

Download SOPS
wget https://github.com/getsops/sops/releases/download/v3.9.3/sops-v3.9.3.linux.amd64
chmod +x sops-v3.9.3.linux.amd64
sudo mv sops-v3.9.3.linux.amd64 /usr/local/bin/sops

**On macOS:**
bash
brew install age sops

**On Windows:**
powershell
Use Windows Package Manager
winget install age
winget install sops

#### 2. Generate Your age Key
Generate a new age key pair. This may complain that the key already exists (created by the make process which is fine)
```
age-keygen -o ~/.config/sops/age/keys.txt
```

View your public key (you'll share this with the team)
```
cat ~/.config/sops/age/keys.txt | grep "public key:"
```

**Important:**
- Keep your private key (`~/.config/sops/age/keys.txt`) secure and backed up
- Share your **public key** with the team lead to be added to `.sops.yaml`
- Never commit your private key to version control

## 📚 Additional documentation

For more details, see the [Detailed Documentation](docs/README.md).

## 🤝 Contributing

We welcome contributions from the community! Please read our [Contributing Guide](CONTRIBUTING.md) for details on:
- How to fork and submit pull requests
- The Contributor License Agreement (CLA) process
- Best practices for contributing to this project
