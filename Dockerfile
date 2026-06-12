# ---- Stage 1: Build Vue.js frontend ----
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.source=https://github.com/markoceri/leapconnect
LABEL org.opencontainers.image.description="LeapConnect - Leapmotor vehicle management webapp"
LABEL org.opencontainers.image.licenses=AGPL-3.0-only

# Install uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /bin/uv && mv /root/.local/bin/uvx /bin/uvx && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY leapconnect/ ./leapconnect/
COPY alembic.ini ./
COPY migrations/ ./migrations/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Data volume for SQLite database
VOLUME ["/app/data"]
ENV HISTORY_DB_PATH=/app/data/leapconnect.db

EXPOSE 8099

CMD ["uv", "run", "uvicorn", "leapconnect.api.app:app", "--host", "0.0.0.0", "--port", "8099"]
