FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.6 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY benchmarks ./benchmarks
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --frozen --no-dev

USER 65532:65532
CMD ["uvicorn", "maintainerflow.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
