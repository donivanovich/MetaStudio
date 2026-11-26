"""FastAPI application entry point for MetaStudio Music Downloader."""

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.api.artwork import router as artwork_router
from backend.api.downloads import router as downloads_router
from backend.api.sessions import router as sessions_router
from backend.api.tags import router as tags_router
from backend.config.settings import get_settings
from backend.services.audio.ffmpeg_service import FFmpegStatus, verify_ffmpeg
from backend.services.classification.classifier import classify_track_enrichment_hook
from backend.services.downloader.ytdlp_service import ytdlp_service
from backend.services.metadata.aggregator import enrich_track_metadata_and_artwork
from backend.services.track_processor import track_processor

logger = logging.getLogger("metastudio")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


class RateLimitMiddleware:
    """Pure ASGI per-IP sliding-window rate limiter (SSE-safe, zero buffering)."""

    def __init__(self, app: ASGIApp, max_requests_per_minute: int = 60) -> None:
        self.app = app
        self.max_requests_per_minute = max_requests_per_minute
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope.get("path", "")
            if path.startswith("/api/") and path != "/api/v1/health":
                client = scope.get("client")
                client_ip = client[0] if client else "unknown"
                now = time.monotonic()
                bucket = self._buckets[client_ip]
                while bucket and now - bucket[0] > 60.0:
                    bucket.popleft()
                if len(bucket) >= self.max_requests_per_minute:
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "detail": (
                                "Demasiadas peticiones. Espera un momento e inténtalo de nuevo."
                            )
                        },
                    )
                    await response(scope, receive, send)
                    return
                bucket.append(now)
        await self.app(scope, receive, send)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application."""
    settings = get_settings()
    cached_ffmpeg: dict[str, FFmpegStatus | None] = {"status": None}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _ = settings.temp_path
        _ = settings.data_path
        status = verify_ffmpeg()
        cached_ffmpeg["status"] = status
        if status.available:
            logger.info("FFmpeg verified (%s): %s", status.source, status.version)
        else:
            logger.warning("FFmpeg NOT available: %s", status.error)
        logger.info("yt-dlp version: %s", ytdlp_service.get_version())
        yield

    app = FastAPI(
        title="MetaStudio Music Downloader API",
        version="1.0.0",
        description="Backend Python (FastAPI + yt-dlp + FFmpeg + Mutagen) para MetaStudio.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        RateLimitMiddleware, max_requests_per_minute=settings.rate_limit_per_minute
    )

    @app.get("/api/v1/health")
    async def health_check():
        status = cached_ffmpeg["status"] or verify_ffmpeg()
        cached_ffmpeg["status"] = status
        return {
            "status": "ok" if status.available else "degraded",
            "ffmpeg": {
                "available": status.available,
                "source": status.source,
                "version": status.version,
                "error": status.error,
            },
            "yt_dlp_version": ytdlp_service.get_version(),
            "providers": {
                "musicbrainz": True,
                "deezer": True,
                "itunes": True,
                "discogs": bool(settings.discogs_token),
            },
        }

    track_processor.register_enrichment_hook(enrich_track_metadata_and_artwork)
    track_processor.register_enrichment_hook(classify_track_enrichment_hook)
    app.include_router(sessions_router)
    app.include_router(artwork_router)
    app.include_router(tags_router)
    app.include_router(downloads_router)

    return app


app = create_app()
