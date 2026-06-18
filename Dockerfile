# Stage 1: build the frontend.
FROM node:20-alpine AS frontend

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: backend runtime that also serves the built frontend.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FRONTEND_DIST=/app/static

WORKDIR /app

# Install dependencies first to leverage Docker layer caching.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# Built SPA, served by FastAPI at "/".
COPY --from=frontend /frontend/dist ./static

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Apply migrations, then start the ASGI app (the top-level wrapper fronts /mcp).
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
