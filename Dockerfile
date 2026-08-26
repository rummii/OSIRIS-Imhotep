# OSIRIS Imhotep - Backend (FastAPI)
# Multi-stage build: builder (with gcc) -> slim runtime (no gcc)
# Image layout (final stage):
#   /app/
#     app/                 <- Python package (main.py, config.py, api/, core/, ...)
#     requirements.txt     <- for traceability
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

# Copy backend CONTENTS (not the directory) so ./app/main.py lands at /app/app/main.py
COPY --chown=appuser:appgroup backend/ ./

# Put pip-installed binaries (uvicorn, etc.) on PATH
ENV PATH=/home/appuser/.local/bin:$PATH
# Make /app importable in case any sub-module does relative-from-root
ENV PYTHONPATH=/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
