# Contributing

1. Install Python 3.12 and `uv`.
2. Run `uv sync --extra dev`.
3. Run `uv run ruff check .`, `uv run mypy src/maintainerflow`, and
   `uv run pytest -m "not e2e"` before opening a pull request.
4. Add tests for every behavior change; never place business logic in API routes or worker actors.

Use focused pull requests. Do not commit `.env`, GitHub secrets, private webhook payloads, or
third-party source code.
