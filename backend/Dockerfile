# ==============================================================================
# MetaStudio Backend — FastAPI + yt-dlp + FFmpeg + Mutagen + Pillow
# ==============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Native FFmpeg/ffprobe for audio extraction & MP3 conversion
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy project configuration and backend source
COPY pyproject.toml ./pyproject.toml
COPY backend ./backend

# Prepare non-root user and writable storage directories (volume mount points)
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && mkdir -p /app/backend/data /app/backend/tmp \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; r = urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4); sys.exit(0 if r.status == 200 else 1)"]

# Single async worker keeps in-memory sessions, SSE subscribers, and download jobs consistent
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
