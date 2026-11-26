"""Endpoints for independent artwork search, custom cover upload, and isolated image serving."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.schemas.api import TrackResponse
from backend.services.artwork.artwork_service import (
    ArtworkValidationError,
    resolve_session_artwork_file,
    save_custom_artwork,
)
from backend.services.metadata.aggregator import enrich_track_metadata_and_artwork
from backend.services.storage.store import session_store

router = APIRouter(prefix="/api/v1", tags=["artwork"])


@router.post("/sessions/{session_id}/tracks/{track_id}/artwork/search", response_model=TrackResponse)
async def refresh_artwork_and_metadata(session_id: str, track_id: str):
    """Trigger an independent metadata & artwork search using the track's current title/artists."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")

    await enrich_track_metadata_and_artwork(session, track)
    session_store.save_session(session)
    return session_store.serialize_track(session, track)


@router.post("/sessions/{session_id}/tracks/{track_id}/artwork/upload", response_model=TrackResponse)
async def upload_custom_artwork(
    session_id: str,
    track_id: str,
    file: Annotated[UploadFile, File(...)],
):
    """Upload and validate a custom cover image for a specific track."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")

    raw = await file.read()
    try:
        save_custom_artwork(session, track, raw)
    except ArtworkValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return session_store.serialize_track(session, track)


@router.get("/sessions/{session_id}/artwork/{filename}")
async def serve_custom_artwork(session_id: str, filename: str):
    """Serve a session-isolated uploaded artwork image."""
    path = resolve_session_artwork_file(session_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail="Carátula no encontrada.")
    return FileResponse(path, media_type="image/jpeg")
