"""Isolated session store, metadata/artwork TTL cache, and persistent tag storage."""

import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from backend.config.settings import get_settings
from backend.models.domain import (
    ArtworkCandidate,
    SessionState,
    TrackState,
    TrackStatus,
)
from backend.schemas.api import SessionResponse, TrackResponse

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class TTLCache:
    """Simple in-memory cache with time-to-live expiration."""

    def __init__(self, ttl_seconds: float = 1800.0, max_entries: int = 512) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._data) >= self._max_entries:
            oldest_key = next(iter(self._data))
            self._data.pop(oldest_key, None)
        self._data[key] = (time.monotonic() + self._ttl, value)

    def clear(self) -> None:
        self._data.clear()


class SessionStore:
    """Manages isolated user sessions, temp directories, and independent tag persistence."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self.metadata_cache = TTLCache(ttl_seconds=3600.0)
        self.artwork_cache = TTLCache(ttl_seconds=3600.0)

    def _validate_session_id(self, session_id: str) -> str:
        if not _UUID_RE.match(session_id):
            raise ValueError("Identificador de sesión inválido.")
        return session_id

    def get_session_dir(self, session_id: str) -> Path:
        """Return an isolated temp directory strictly bound to `session_id`."""
        valid_id = self._validate_session_id(session_id)
        base = get_settings().temp_path.resolve()
        session_dir = (base / valid_id).resolve()
        if base not in session_dir.parents:
            raise ValueError("Acceso fuera del directorio de sesión bloqueado.")
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir

    def create_session(
        self,
        *,
        source_url: str,
        platform: str,
        is_playlist: bool,
        playlist_title: str | None,
        notice: str | None,
        tracks: list[TrackState],
    ) -> SessionState:
        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            source_url=source_url,
            platform=platform,
            is_playlist=is_playlist,
            playlist_title=playlist_title,
            notice=notice,
            tracks=tracks,
            queue_track_ids=[t.id for t in tracks],
        )
        self._sessions[session_id] = session
        self.get_session_dir(session_id)
        self._save_session_snapshot(session)
        return session

    def get_session(self, session_id: str) -> SessionState | None:
        if not _UUID_RE.match(session_id):
            return None
        session = self._sessions.get(session_id)
        if session is not None:
            return session
        # Restore snapshot if persisted on disk
        snapshot = self._snapshot_path(session_id)
        if snapshot.is_file():
            try:
                loaded = SessionState.model_validate_json(snapshot.read_text(encoding="utf-8"))
                self._sessions[session_id] = loaded
                return loaded
            except Exception as exc:
                logger.warning("Failed to reload session snapshot %s: %s", session_id, exc)
        return None

    def save_session(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session
        self._save_session_snapshot(session)

    def _snapshot_path(self, session_id: str) -> Path:
        return get_settings().data_path / "sessions" / f"{session_id}.json"

    def _save_session_snapshot(self, session: SessionState) -> None:
        try:
            path = self._snapshot_path(session.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(session.model_dump_json(indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not persist session snapshot: %s", exc)

    # --- Independent Track Tag Persistence (reusable across future apps) ---

    def _tags_file(self) -> Path:
        return get_settings().data_path / "track_tags.json"

    def load_persisted_tags(self, track_key: str) -> list[str]:
        path = self._tags_file()
        if not path.is_file():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            entry = data.get("tracks", {}).get(track_key)
            if isinstance(entry, dict) and isinstance(entry.get("tag_ids"), list):
                return [str(tid) for tid in entry["tag_ids"]]
        except Exception as exc:
            logger.warning("Failed to read track_tags.json: %s", exc)
        return []

    def persist_track_tags(self, track_key: str, tag_ids: list[str], title: str = "") -> None:
        path = self._tags_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"catalog_version": "1.0.0", "tracks": {}}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
                    payload.setdefault("tracks", {})
            except Exception:
                pass
        deduped = list(dict.fromkeys(tag_ids))
        payload["tracks"][track_key] = {
            "tag_ids": deduped,
            "title": title,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Metadata Update Rules (Rules 8.1 & 8.2) ---

    def update_track_metadata(
        self,
        session: SessionState,
        track: TrackState,
        *,
        title: str | None = None,
        artists: list[str] | None = None,
        artists_text: str | None = None,
        album: str | None = None,
        selected_artwork_id: str | None = None,
    ) -> TrackState:
        """Apply user edits strictly to the 4 permitted metadata fields with album auto-sync."""
        if title is not None:
            cleaned_title = title.strip()
            if cleaned_title:
                track.title = cleaned_title
                track.metadata_provenance["title"] = "manual"
                # Rule 8.1: sync album automatically ONLY if still auto-synced
                if track.album_auto_synced:
                    track.album = cleaned_title
                    track.metadata_provenance["album"] = "auto_from_title"

        if artists is not None:
            cleaned_list = [a.strip() for a in artists if a and a.strip()]
            track.artists = cleaned_list
            track.metadata_provenance["artists"] = "manual"
        elif artists_text is not None:
            # Rule 8.2: split comma-space separated artists from UI text input
            parsed = [part.strip() for part in artists_text.split(",") if part.strip()]
            track.artists = parsed
            track.metadata_provenance["artists"] = "manual"

        if album is not None:
            cleaned_album = album.strip()
            if not cleaned_album:
                # Empty album falls back to track title and re-enables auto-sync
                track.album = track.title
                track.album_auto_synced = True
                track.metadata_provenance["album"] = "auto_from_title"
            else:
                track.album = cleaned_album
                track.album_auto_synced = False
                track.metadata_provenance["album"] = "manual"

        if selected_artwork_id is not None:
            matched = False
            for art in track.artwork_candidates:
                art.selected = art.id == selected_artwork_id
                if art.selected:
                    matched = True
                    track.selected_artwork_id = art.id
                    track.metadata_provenance["artwork"] = art.source
            if not matched:
                raise ValueError("La carátula seleccionada no existe para esta canción.")

        self.save_session(session)
        return track

    def serialize_track(self, session: SessionState, track: TrackState) -> TrackResponse:
        """Convert domain TrackState into safe frontend TrackResponse."""
        selected_url = None
        safe_artworks: list[ArtworkCandidate] = []
        for art in track.artwork_candidates:
            public_art = art.model_copy(update={"local_path": None})
            safe_artworks.append(public_art)
            if art.id == track.selected_artwork_id or art.selected:
                selected_url = public_art.url

        download_url = None
        if track.downloaded_file_name and track.status == TrackStatus.DOWNLOADED:
            download_url = f"/api/v1/sessions/{session.session_id}/tracks/{track.id}/file"

        return TrackResponse(
            id=track.id,
            index=track.index,
            source_id=track.source_id,
            source_url=track.source_url,
            platform=track.platform,
            audio_downloadable=track.audio_downloadable,
            status=track.status,
            error_message=track.error_message,
            title=track.title,
            artists=track.artists,
            artists_display=track.artists_display,
            album=track.album or track.title,
            album_auto_synced=track.album_auto_synced,
            selected_artwork_id=track.selected_artwork_id,
            selected_artwork_url=selected_url,
            duration_seconds=track.duration_seconds,
            preview_audio_url=track.preview_audio_url,
            metadata_candidates=track.metadata_candidates,
            artwork_candidates=safe_artworks,
            suggested_tags=track.suggested_tags,
            selected_tag_ids=track.selected_tag_ids,
            metadata_provenance=track.metadata_provenance,
            in_queue=track.id in session.queue_track_ids,
            download_progress=track.download_progress,
            downloaded_file_name=track.downloaded_file_name,
            download_url=download_url,
        )

    def serialize_session(self, session: SessionState) -> SessionResponse:
        processed = sum(
            1
            for t in session.tracks
            if t.status in {TrackStatus.READY, TrackStatus.DOWNLOADING, TrackStatus.DOWNLOADED}
        )
        return SessionResponse(
            session_id=session.session_id,
            source_url=session.source_url,
            platform=session.platform,
            is_playlist=session.is_playlist,
            playlist_title=session.playlist_title,
            notice=session.notice,
            total_tracks=len(session.tracks),
            processed_tracks=processed,
            queue_track_ids=list(session.queue_track_ids),
            tracks=[self.serialize_track(session, t) for t in session.tracks],
        )


session_store = SessionStore()
