# Repository Guidelines

## Project Structure & Module Organization
- `pybt/` holds the core package. Key modules live under `core/` (engine, event bus, models), `data/` (feeds/adapters), `strategies/`, `portfolio/`, `execution/`, `risk/`, and `analytics/`.
- `tests/` contains pytest suites; `examples/` includes end-to-end scripts; `docs/` holds design notes.
- Runtime assets and artifacts typically land in `data/`, `assets/`, and `artifacts/`.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` sets up a local venv.
- `pip install -e .[dev]` installs dev tools; optional extras: `.[data]` (pandas) and `.[realtime]` (adata, requests, websockets).
- `pytest -q` runs the full test suite.
- `python -m pybt --config ./config.json --log-level INFO --json-logs` runs a configured backtest from JSON.
- `black .` formats code; `mypy pybt` checks static types.

## Coding Style & Naming Conventions
- Python 3.10+ with `black` (line length 88). Keep modules, functions, and variables in `snake_case`; classes in `CamelCase`; constants in `UPPER_SNAKE_CASE`.
- Mypy is configured with `disallow_untyped_defs=true`, so new functions should be typed.
- Keep comments focused on business logic; avoid trivial commentary.

## Testing Guidelines
- Tests are pytest-based and should live in `tests/` with `test_*.py` naming.
- Use simple, verifiable synthetic data for test fixtures; avoid duplicating production logic.
- Coverage tooling (`pytest-cov`) is available, but no hard threshold is configured.

## Commit & Pull Request Guidelines
- Recent history uses version-prefixed messages like `v0.x: <short summary>` (often in Chinese). Follow that pattern unless the team changes it.
- PRs should include a concise description, the tests run (or a reason for skipping), and any config or data changes.

## Agent-Specific Instructions
- Follow the rules in `agent.md` (and `agent.zh-cn.md` if needed) for style, testing, and refactoring expectations.
