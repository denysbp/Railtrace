FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY backend ./backend
RUN uv sync --locked --no-dev

ENV API_PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "fastapi run backend/app/main.py --host 0.0.0.0 --port ${API_PORT}"]
