"""Endpoints for URL analysis, playlist sessions, lazy track processing, metadata edits, and queue."""

import asyncio
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Query

from backend.models.domain import ArtworkCandidate, TrackState, TrackStatus
from backend.schemas.api import (
    AnalyzeRequest,
    ApplyCandidateRequest,
    SessionResponse,
    TrackResponse,
    UpdateMetadataRequest,
)
from backend.services.downloader.ytdlp_service import DownloadServiceError, ytdlp_service
from backend.services.metadata.providers import fetch_spotify_oembed
from backend.services.storage.store import session_store
from backend.services.track_processor import track_processor
from backend.utils.metadata_normalizer import normalize_album_name, normalize_title_and_artists
from backend.utils.url_validator import URLValidationError, validate_url

router = APIRouter(prefix="/api/v1", tags=["sessions"])


def _require_session_and_track(session_id: str, track_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada en la sesión.")
    return session, track


@router.post("/analyze", response_model=SessionResponse)
async def analyze_url(payload: AnalyzeRequest):
    """Analyze a single track or playlist URL with lazy loading (processes ONLY track 0)."""
    try:
        validated = validate_url(payload.url)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # DRM platforms (Spotify / Apple Music / Deezer): honest metadata-only session
    if validated.metadata_only:
        fallback_title = validated.url.rsplit("/", 1)[-1].split("?")[0] or "Track"
        init_title = fallback_title
        init_artists: list[str] = []
        init_candidates = []
        init_artworks: list[ArtworkCandidate] = []
        selected_art_id: str | None = None
        init_prov: dict[str, str] = {}

        # Extract official public title & cover from Spotify oEmbed whenever a Spotify URL is pasted
        if validated.platform == "spotify":
            async with httpx.AsyncClient(follow_redirects=True) as client:
                sp_oembed = await fetch_spotify_oembed(client, validated.url)
            if sp_oembed is not None:
                init_title = sp_oembed.title or fallback_title
                init_artists = list(sp_oembed.artists)
                init_candidates.append(sp_oembed)
                init_prov["title"] = "Spotify"
                if init_artists:
                    init_prov["artists"] = "Spotify"
                if sp_oembed.artwork_url:
                    art_id = f"art-{uuid.uuid4().hex[:8]}"
                    init_artworks.append(
                        ArtworkCandidate(
                            id=art_id,
                            source="Spotify",
                            url=sp_oembed.artwork_url,
                            width=300,
                            height=300,
                            format="jpeg",
                            selected=True,
                        )
                    )
                    selected_art_id = art_id
                    init_prov["artwork"] = "Spotify"

        track = TrackState(
            id=f"trk-{uuid.uuid4().hex[:10]}",
            index=0,
            source_id=validated.url,
            source_url=validated.url,
            platform=validated.platform,
            audio_downloadable=False,
            status=TrackStatus.PENDING,
            raw_title=init_title,
            title=init_title,
            artists=init_artists,
            album="",
            album_auto_synced=True,
            selected_artwork_id=selected_art_id,
            artwork_candidates=init_artworks,
            metadata_candidates=init_candidates,
            metadata_provenance=init_prov,
        )
        session = session_store.create_session(
            source_url=validated.url,
            platform=validated.platform,
            is_playlist=validated.is_playlist_hint,
            playlist_title=None,
            notice=validated.notice,
            tracks=[track],
        )
        await track_processor.process_track(session, track)
        return session_store.serialize_session(session)

    try:
        summary = await asyncio.to_thread(ytdlp_service.extract_url, validated.url)
    except DownloadServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    tracks: list[TrackState] = []
    for idx, entry in enumerate(summary.entries):
        art_candidates: list[ArtworkCandidate] = []
        selected_art_id: str | None = None
        if entry.thumbnail_url:
            art_id = f"art-{uuid.uuid4().hex[:8]}"
            art_source = (
                "YouTube Music"
                if validated.platform == "youtube_music"
                else (
                    "YouTube"
                    if not entry.extractor or entry.extractor.lower() == "youtube"
                    else entry.extractor
                )
            )
            art_candidates.append(
                ArtworkCandidate(
                    id=art_id,
                    source=art_source,
                    url=entry.thumbnail_url,
                    format="jpeg",
                    selected=True,
                )
            )
            selected_art_id = art_id

        initial_album = entry.album or entry.title
        album_auto = not bool(entry.album)
        tracks.append(
            TrackState(
                id=f"trk-{uuid.uuid4().hex[:10]}",
                index=idx,
                source_id=entry.source_id,
                source_url=entry.url,
                platform=validated.platform,
                audio_downloadable=True,
                status=TrackStatus.PENDING,
                raw_title=entry.raw_title,
                title=entry.title,
                artists=entry.artists,
                album=initial_album,
                album_auto_synced=album_auto,
                selected_artwork_id=selected_art_id,
                duration_seconds=entry.duration_seconds,
                preview_audio_url=entry.preview_audio_url,
                original_genres=entry.original_genres,
                original_language=entry.original_language,
                artwork_candidates=art_candidates,
                metadata_provenance={
                    "title": entry.extractor or "yt-dlp",
                    "artists": entry.extractor or "yt-dlp",
                    "album": (entry.extractor or "yt-dlp") if entry.album else "auto_from_title",
                },
            )
        )

    session = session_store.create_session(
        source_url=validated.url,
        platform=validated.platform,
        is_playlist=summary.is_playlist,
        playlist_title=summary.playlist_title,
        notice=validated.notice,
        tracks=tracks,
    )

    # Mandatory lazy-loading rule: process ONLY the first track initially
    if session.tracks:
        await track_processor.process_track(session, session.tracks[0])

    return session_store.serialize_session(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return session_store.serialize_session(session)


@router.get("/sessions/{session_id}/tracks/{track_id}", response_model=TrackResponse)
async def get_track(session_id: str, track_id: str):
    session, track = _require_session_and_track(session_id, track_id)
    return session_store.serialize_track(session, track)


@router.post("/sessions/{session_id}/tracks/{track_id}/process", response_model=TrackResponse)
async def process_track_on_demand(
    session_id: str,
    track_id: str,
    force: bool = Query(default=False, description="Forzar reprocesamiento o reintento tras error"),
):
    """Lazy-load full metadata, artwork, and smart tag suggestions for a specific track."""
    session, track = _require_session_and_track(session_id, track_id)
    await track_processor.process_track(session, track, force=force)
    return session_store.serialize_track(session, track)


@router.patch("/sessions/{session_id}/tracks/{track_id}/metadata", response_model=TrackResponse)
async def update_track_metadata(
    session_id: str,
    track_id: str,
    payload: UpdateMetadataRequest,
):
    """Update ONLY the four permitted metadata fields (title, artists, album, artwork)."""
    session, track = _require_session_and_track(session_id, track_id)
    try:
        updated = session_store.update_track_metadata(
            session,
            track,
            title=payload.title,
            artists=payload.artists,
            artists_text=payload.artists_text,
            album=payload.album,
            selected_artwork_id=payload.selected_artwork_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session_store.serialize_track(session, updated)


@router.post("/sessions/{session_id}/tracks/{track_id}/apply-candidate", response_model=TrackResponse)
async def apply_metadata_candidate(
    session_id: str,
    track_id: str,
    payload: ApplyCandidateRequest,
):
    """Apply selected fields (or all 3 text fields) from a specific metadata source candidate."""
    session, track = _require_session_and_track(session_id, track_id)
    candidate = next(
        (c for c in track.metadata_candidates if c.source.lower() == payload.source.lower()),
        None,
    )
    if not candidate:
        raise HTTPException(status_code=404, detail="Proveedor de metadatos no encontrado.")

    fields = set(payload.fields) if payload.fields else {"title", "artists", "album"}
    clean_cand_title, clean_cand_artists = normalize_title_and_artists(
        candidate.title, candidate.artists, structured_artists=True
    )
    clean_cand_album = normalize_album_name(candidate.album)
    if "title" in fields and clean_cand_title:
        track.title = clean_cand_title
        track.metadata_provenance["title"] = candidate.source
        if track.album_auto_synced and "album" not in fields:
            track.album = clean_cand_title
    if "artists" in fields and clean_cand_artists:
        track.artists = list(clean_cand_artists)
        track.metadata_provenance["artists"] = candidate.source
    if "album" in fields:
        if clean_cand_album:
            track.album = clean_cand_album
            track.album_auto_synced = False
            track.metadata_provenance["album"] = candidate.source
        else:
            track.album = track.title
            track.album_auto_synced = True
            track.metadata_provenance["album"] = "auto_from_title"

    session_store.save_session(session)
    return session_store.serialize_track(session, track)


@router.delete("/sessions/{session_id}/queue/{track_id}", response_model=SessionResponse)
async def remove_track_from_queue(session_id: str, track_id: str):
    """Remove a track from the independent download queue without modifying the original playlist."""
    session, _track = _require_session_and_track(session_id, track_id)
    session.queue_track_ids = [tid for tid in session.queue_track_ids if tid != track_id]
    session_store.save_session(session)
    return session_store.serialize_session(session)


@router.post("/sessions/{session_id}/queue/{track_id}", response_model=SessionResponse)
async def restore_track_to_queue(session_id: str, track_id: str):
    """Re-add a playlist track back into the independent download queue."""
    session, _track = _require_session_and_track(session_id, track_id)
    if track_id not in session.queue_track_ids:
        # Preserve original playlist order
        ordered = [t.id for t in session.tracks if t.id in session.queue_track_ids or t.id == track_id]
        session.queue_track_ids = ordered
        session_store.save_session(session)
    return session_store.serialize_session(session)
