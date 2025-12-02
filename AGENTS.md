# Repository Guidelines

## Project Structure & Module Organization
The repo is split between a FastAPI backend in `backend/src` and a React/Vite frontend in `frontend/src`. Domain logic for encounters and game state lives under `backend/src/game`, while API routers are grouped in `backend/src/api`. Backend tests stay in `backend/test`, and end-to-end samples sit in `backend/examples`. The frontend keeps UI components under `frontend/src/components`, state and hooks in `frontend/src/state`, and Vitest suites under `frontend/tests` (mirroring `unit/` and `integration/`). Shared services such as authentication, persistence, and campaign storage are broken out into the top-level `auth/`, `db/`, and `campaign_storage/` packages, with deeper architectural notes in `docs/` (start with `docs/SETUP.md` and `docs/ARCHITECTURE.md`). Audio services run from `speech-to-text/` and `tts-service/` when voice features are enabled.

## Build, Test, and Development Commands
- `cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt` prepares the backend environment.
- `cd backend && python run_uvicorn.py` starts the FastAPI server with autoreload.
- `cd backend && python run_tests.py [-c|--markers unit]` wraps pytest with common env flags; add `-c` for coverage output.
- `cd frontend && npm install` restores the Vite workspace.
- `cd frontend && npm run dev` serves the React app; `npm run build` emits the production bundle, and `npm run preview` validates it locally.
- `cd frontend && npm run lint` applies the repository ESLint rules before raising a PR.

## Coding Style & Naming Conventions
Python modules follow PEP 8 with 4-space indentation, explicit type hints for public interfaces, and snake_case filenames (see `backend/src/api/main.py`). Keep FastAPI routes grouped by feature under `api/<feature>/router.py`. React files use PascalCase for components, camelCase for hooks and utilities, and co-locate CSS or Tailwind modules with the component. Run `npm run lint` and favor small, pure functions; server-side code should include docstrings explaining external dependencies. Secrets belong in `.env` files referenced via `dotenv`—never hard-code them.

## Testing Guidelines
Default backend coverage comes from `pytest` (configured via `backend/pytest.ini`). Mark slow or integration scenarios using `@pytest.mark.slow` or `@pytest.mark.integration` so CI can filter them with `python run_tests.py --markers "not slow"`. Frontend tests use Vitest with Testing Library; place component specs in `frontend/tests/unit` and API/Router specs in `frontend/tests/integration`. Run `npm run test` for watch mode or `npm run test:coverage` before merges. Add fixtures in `frontend/tests/fixtures` or `backend/test/conftest.py` instead of inline mocks to keep suites reusable.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit messages (e.g., `Fix turn status`) with optional issue references (`#123`). Group related backend and frontend changes separately to aid reviewers. For pull requests, include: concise summary, impacted modules (`backend/src/game/...`), testing proof (`python run_tests.py`, `npm run test:run`), and screenshots for UI changes. Mention any new environment variables or migrations, and link relevant docs if you touched architecture decisions.

## Configuration Tips
Copy `.env.example` files when present and load them with `backend/src/main.py`. Use `setup_shared_modules.sh` if you need local symlinks into `auth/` or `db/`. Voice features require the auxiliary services (`speech-to-text`, `tts-service`)—run them via their Dockerfiles only when needed to keep the core loop lightweight.
