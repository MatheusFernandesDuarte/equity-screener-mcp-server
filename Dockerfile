# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1 \
    PYTHONDONTWRITEBYTECODE=1

# deps mínimas para build de wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# instalar uv
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src ./src
COPY run.py ./run.py

# --- Stage 2: Tester ---
FROM builder AS tester
RUN uv run pytest tests/

# --- Stage 3: Runtime ---
FROM python:3.11-slim AS runtime

WORKDIR /app

# somente libs necessárias para o Chromium rodar
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    libnss3 \
    libglib2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libxkbcommon0 \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# usuário não-root
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
