# OSIRIS Imhotep - Backend (FastAPI)
# Multi-stage build: builder (with gcc) -> slim runtime (no gcc)
# Image layout (final stage):
#   /app/
#     app/                 <- Python package (main.py, config.py, api/, core/, ...)
#     requirements.txt
#   /home/appuser/.local/  <- pip packages

FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.11-slim

WORKDIR /app

# Install runtime Postgres client libs (no dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd  --uid 1001 --gid appgroup --shell /bin/bash appuser

# Copy installed packages
COPY --from=builder /root/.local /home/appuser/.local

# Copy backend/ CONTENTS into /app/ so backend/app/main.py -> /app/app/main.py
# Trailing slash on SOURCE (backend/) is critical: it means "contents of backend/"
COPY --chown=appuser:appgroup backend/ ./

# Put pip binaries (uvicorn) on PATH + make /app importable
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app

USER appuser

# Cloud Run probes port 8080 by default; align with that
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# uvicorn listens on 8080 to match Cloud Run health check
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
