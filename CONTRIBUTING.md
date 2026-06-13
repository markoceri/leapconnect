# Contributing to LeapConnect

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)
- Node.js (for the frontend)

### Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

See [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for other methods (Homebrew, Windows, pipx).

### Backend

```bash
uv sync
uv run pre-commit install && uv run pre-commit install --hook-type pre-push
uv run uvicorn leapconnect.api.app:app --host 0.0.0.0 --port 8099 --reload
```

The API runs at **http://localhost:8099**.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vue dev server runs at **http://localhost:5173** and proxies `/api` calls to the backend.

### Production build (manual)

```bash
cd frontend
npm run build
```

This outputs to `frontend/dist/`. The FastAPI backend will automatically serve the built SPA.

## Project Structure

```
├── leapconnect/         # Python backend (hexagonal layout)
│   ├── domain/          # Pure business logic (bounded contexts)
│   ├── application/     # Use cases, scheduler, ports
│   ├── infrastructure/  # SQLite, MQTT, Telegram, ABRP adapters
│   ├── api/             # FastAPI app factory, routers, DTOs
│   └── container.py     # Composition root
├── migrations/          # Alembic database migrations
├── tests/               # Pytest test suite
└── frontend/            # Vue.js 3 SPA
    └── src/
        ├── App.vue
        ├── components/  # Reusable UI components
        ├── composables/ # Vue composables (API, toast)
        ├── stores/      # Pinia stores
        ├── utils/       # Formatting utilities
        └── views/       # Page-level views (tabs, setup wizards)
```

## Tests

```bash
uv run pytest
```

## Code Quality

Pre-commit hooks run automatically:

- **On commit**: trailing whitespace, end-of-file fix, YAML/TOML/JSON validation, ruff lint + format
- **On push**: full pytest suite

To run all checks manually:

```bash
uv run pre-commit run --all-files
```

## Versioning

The project uses [bump-my-version](https://github.com/callowayproject/bump-my-version) to manage versions across `pyproject.toml` and `frontend/package.json`.

```bash
uv run bump-my-version bump patch   # 0.1.0 → 0.1.1 (bugfix)
uv run bump-my-version bump minor   # 0.1.0 → 0.2.0 (new feature)
uv run bump-my-version bump major   # 0.1.0 → 1.0.0 (breaking change)
```

Each command updates the version in both files, creates a commit, and tags it `vX.Y.Z`.

**Release workflow:**

1. Commit all changes
2. Update `CHANGELOG.md` (move entries from `[Unreleased]` to a new version section)
3. `uv run bump-my-version bump patch|minor|major`
4. `git push --follow-tags`

## Pull Request Guidelines

### Before you start

- Check the [issue tracker](https://github.com/markoceri/leapconnect/issues) for existing issues or feature requests.
- For new features or significant changes, open an issue first to discuss the approach.

### PR requirements

- Keep changes small and focused — one concern per PR.
- Add or update tests for any new functionality.
- Ensure all checks pass: `uv run pytest`, `uv run pre-commit run --all-files`.
- Follow the existing code style — the project uses [Ruff](https://github.com/astral-sh/ruff) for formatting and linting.

### Commit messages

Use [conventional commits](https://www.conventionalcommits.org/):

- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation changes
- `chore:` maintenance, dependency updates
- `refactor:` code restructuring without behavior change
- `test:` adding or updating tests

## Code Style

- **Ruff** for linting and formatting (configured in `pyproject.toml`).
- **Vue.js 3** Composition API with `<script setup>` for frontend components.
- **Tailwind CSS** for styling.
