# ---- Stage 1: Build Vue.js frontend ----
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM python:3.13-slim AS runtime

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy application code
COPY main.py ./
COPY persistence/ ./persistence/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Data volume for SQLite database
VOLUME ["/app/data"]
ENV HISTORY_DB_PATH=/app/data/history.db

EXPOSE 8099

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099"]
