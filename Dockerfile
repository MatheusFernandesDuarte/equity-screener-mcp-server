# --- Stage 1: Builder ---
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY src ./src
COPY run.py ./run.py
COPY tests ./tests

# --- Stage 2: Tester ---
FROM builder AS tester
RUN apt-get update && apt-get install -y chromium-driver chromium
RUN uv run pytest tests/

# --- Stage 3: Runtime ---
FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libnss3 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN useradd -m -u 1000 app

COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/src ./src
COPY --from=builder /app/run.py ./run.py

RUN mkdir -p data/outputs && chown -R app:app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/app

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

USER app

ENTRYPOINT ["python", "run.py"]