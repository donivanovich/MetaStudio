"""Endpoints for the independent versioned tag catalog and per-track smart tags."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.schemas.api import TrackResponse, UpdateTagsRequest
from backend.services.classification.catalog import tag_catalog
from backend.services.classification.classifier import classify_track
from backend.services.storage.store import session_store

router = APIRouter(prefix="/api/v1", tags=["tags"])


class CreateCustomTagRequest(BaseModel):
    category: str = Field(..., pattern="^(language|mood)$")
    name: str = Field(..., min_length=1, max_length=40)


@router.get("/tags/catalog")
async def get_tag_catalog():
    """Return the full centralized, versioned catalog of language and mood tags."""
    return tag_catalog.export_catalog()


@router.post("/tags/catalog")
async def create_custom_tag(payload: CreateCustomTagRequest):
    """Extend the tag catalog with a custom language or mood tag."""
    try:
        tag = tag_catalog.register_custom_tag(category=payload.category, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"tag": tag.to_dict(), "catalog": tag_catalog.export_catalog()}


@router.get("/sessions/{session_id}/tracks/{track_id}/tags")
async def get_track_tags(session_id: str, track_id: str):
    """Return suggested and selected tags for a track (never written into MP3 ID3)."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")

    if not track.suggested_tags:
        track.suggested_tags = classify_track(
            title=track.title,
            artists=track.artists,
            original_genres=track.original_genres,
            original_language=track.original_language,
        )
        session_store.save_session(session)

    return {
        "track_id": track.id,
        "suggested_tags": [s.model_dump() for s in track.suggested_tags],
        "selected_tag_ids": track.selected_tag_ids,
    }


@router.put("/sessions/{session_id}/tracks/{track_id}/tags", response_model=TrackResponse)
async def update_track_tags(
    session_id: str,
    track_id: str,
    payload: UpdateTagsRequest,
):
    """Update and independently persist selected tag IDs for a track."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")

    all_tags = tag_catalog.all_tags()
    valid_ids = [tid for tid in dict.fromkeys(payload.tag_ids) if tid in all_tags]
    track.selected_tag_ids = valid_ids
    session_store.persist_track_tags(track.source_url, valid_ids, title=track.title)
    session_store.save_session(session)
    return session_store.serialize_track(session, track)
