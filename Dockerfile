# --- Stage 1: build the React frontend -------------------------------------------------
FROM node:22.23.2-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Stage 2: FastAPI app that also serves the built frontend --------------------------
FROM python:3.12.14-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    STORAGE_BACKEND=gcp
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ backend/
COPY demo/docs/ demo/docs/
COPY demo/recorded/ demo/recorded/
COPY --from=ui /ui/dist/ frontend/dist/

RUN useradd --create-home --uid 10001 saath && chown -R saath /app
USER saath

# Cloud Run sets PORT; sh -c so ${PORT} expands, exec so uvicorn receives signals.
CMD ["sh", "-c", "exec uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT} --timeout-keep-alive 75"]
