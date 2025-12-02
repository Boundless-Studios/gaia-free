# Gaia - AI-Powered D&D Campaign Manager

An intelligent Dungeon Master powered by AI that manages D&D campaigns with automatic agent handoffs for different aspects of gameplay.

## Provider Configuration

Gaia supports both Ollama (local) and Claude (cloud) providers. You can switch between them using environment variables:

### Using Ollama (Default)
```bash
# No environment variables needed - uses Ollama by default
python start_gaia_launcher.py
```

### Using Claude
```bash
# Set environment variables for Claude
export CLAUDE_API_KEY="your-claude-api-key"
export PROVIDER="claude"
export CLAUDE_MODEL="claude-3-opus-20240229"  # Optional, defaults to claude-3-opus-20240229

python start_gaia_launcher.py
```

### Environment Variables

- `PROVIDER`: Set to "ollama" or "claude" (default: "ollama")
- `CLAUDE_API_KEY`: Your Claude API key (required for Claude provider)
- `CLAUDE_MODEL`: Claude model name (default: "claude-3-opus-20240229")
- `CLAUDE_BASE_URL`: Claude API base URL (default: "https://api.anthropic.com/v1")

### Agent Model Selection

When using agents as tools, each agent can use a different model than the parent:
- The main DungeonMasterAgent uses the selected provider/model
- Tool agents (SceneCreator, EncounterRunner, RuleEnforcer) inherit the provider but can be configured with different models
- This allows for specialized models for different tasks (e.g., Claude for main DM, Ollama for rule enforcement)

## 🚀 Quick Start

### One-Click Setup (Cross-Platform)

**All Platforms:**
```bash
python start_gaia_launcher.py
```

## 📋 Prerequisites

Before running Gaia, make sure you have:

1. **Python 3.8+** - [Download here](https://python.org/)
2. **Node.js 16+** - [Download here](https://nodejs.org/)
3. **Ollama**      - [Download here](https://ollama.ai/)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Gaia
   ```

2. **Run the startup script:**
   ```bash
   python start_gaia_launcher.py
   ```

The startup script will:
- ✅ Create a Python virtual environment automatically
- ✅ Install all Python dependencies in the virtual environment
- 🎨 Create a React frontend (if it doesn't exist)
- 📦 Install frontend dependencies
- 🚀 Start both backend and frontend servers
- 🌐 Open your browser automatically

## 🎮 Usage

Once Gaia is running:

1. **Frontend:** http://localhost:3000
2. **Backend API:** http://localhost:8000
3. **API Documentation:** http://localhost:8000/docs

### Starting a Campaign

1. Click "Start New Campaign" to begin a new D&D adventure
2. Type your actions and responses in the chat interface
3. Gaia will automatically handoff between different AI agents:
   - **Dungeon Master:** Manages the overall story and world
   - **Rule Enforcer:** Handles D&D rule clarifications
   - **Turn Runner:** Manages combat and initiative
   - **Narrator:** Provides atmospheric descriptions

### Example Commands

- "I want to start a new D&D campaign"
- "We encounter a group of goblins in the forest"
- "I attack the goblin with my sword"
- "Can I use my bonus action to cast a spell?"

## 🏗️ Architecture

```
Gaia/
├── src/               # Main source code
│   ├── core/          # Core functionality (agents, session, llm, audio)
│   ├── game/          # Game-specific components (D&D agents, engine)
│   ├── api/           # FastAPI backend and endpoints
│   ├── utils/         # Utility functions
│   └── frontend/      # React frontend application (Vite)
├── docs/              # Documentation
├── scripts/           # Utility scripts
├── examples/          # Example usage
├── start_gaia_launcher.py      # Cross-platform startup script
└── requirements.txt   # Python dependencies
```

For detailed file structure, see [FILE_STRUCTURE.md](FILE_STRUCTURE.md).

## 🔧 Development

### Backend Development

The backend is built with FastAPI and provides RESTful APIs for:
- Chat with the D&D orchestrator
- Campaign management
- Agent statistics
- Streaming responses

### Frontend Development

The frontend is a React application that provides:
- Real-time chat interface
- Campaign management UI
- Responsive design
- Dark theme optimized for gaming

### Adding New Agents

To add new D&D agents:

1. Create a new agent class in `src/game/dnd_agents/`
2. Implement the required methods
3. Update the orchestrator to handle handoffs
4. Update the module's `__init__.py` to export the new agent

## 🐛 Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Kill processes on ports 3000 and 8000
# Windows:
netstat -ano | findstr :3000
netstat -ano | findstr :8000

# Linux/macOS:
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

**Node.js not found:**
- Install Node.js from https://nodejs.org/
- Make sure it's added to your PATH

**Python dependencies missing:**
```bash
# The startup script creates a virtual environment automatically
# If you need to install dependencies manually:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Ollama not running:**
- Install Ollama from https://ollama.ai/
- Start the Ollama service
- Pull a model: `ollama pull llama3.2:3b`

### Logs

Gaia uses a sophisticated logging system that separates application logs from third-party noise:

**Log Files:**
- `src/logs/gaia_app.log` - Application logs only (Gaia code)
- `src/logs/gaia_all.log` - All logs (including third-party libraries)
- `src/logs/tool_usage.log` - Tool usage and agent interactions
- `src/logs/gaia_backend.log` - Legacy backend logs

**Console Output:**
- Only Gaia application logs are shown in the console
- OpenAI SDK and other third-party noise is suppressed
- Clean, focused output for development

**Viewing Logs:**
```bash
# Use the log viewer utility
python view_logs.py

# Or view directly
tail -f src/logs/gaia_app.log    # Application logs only
tail -f src/logs/gaia_all.log    # All logs including third-party
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎲 Features

- **Intelligent Agent Handoffs:** Automatic switching between specialized AI agents
- **Real-time Chat:** Stream responses with thinking visibility
- **Campaign Management:** Start and manage D&D campaigns
- **Rule Enforcement:** Automatic D&D rule checking and clarification
- **Combat Management:** Initiative tracking and turn management
- **Responsive UI:** Modern, dark-themed interface
- **API Documentation:** Auto-generated FastAPI docs

## 🔮 Roadmap

- [ ] Character sheet integration
- [ ] Map and battle grid support
- [ ] Voice chat integration
- [ ] Multiplayer support
- [ ] Campaign persistence
- [ ] Custom rule sets
- [ ] Integration with D&D Beyond API
