"""Core domain models for sessions, tracks, metadata candidates, artwork, and tags."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TrackStatus(StrEnum):
    """Lifecycle states for each track in a session."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    ERROR = "error"


class MetadataSourceCandidate(BaseModel):
    """Normalized metadata match returned by a music provider."""

    source: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str | None = None
    duration_seconds: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    external_id: str | None = None
    genres: list[str] = Field(default_factory=list)
    language: str | None = None
    preview_url: str | None = None
    artwork_url: str | None = None
    provenance: dict[str, str] = Field(default_factory=dict)

    @property
    def artists_display(self) -> str:
        return ", ".join(self.artists)


class ArtworkCandidate(BaseModel):
    """Normalized artwork option available for a track."""

    id: str
    source: str
    url: str
    width: int | None = None
    height: int | None = None
    format: str = "jpeg"
    is_custom: bool = False
    local_path: str | None = None
    selected: bool = False


class TagSuggestion(BaseModel):
    """Smart language or mood tag suggestion with provenance and confidence."""

    tag_id: str
    category: str  # "language" | "mood"
    name: str
    display_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    rationale: str | None = None


class TrackState(BaseModel):
    """Full stateful representation of a single track inside a session."""

    id: str
    index: int
    source_id: str
    source_url: str
    platform: str
    audio_downloadable: bool = True
    status: TrackStatus = TrackStatus.PENDING
    error_message: str | None = None

    raw_title: str
    title: str
    artists: list[str] = Field(default_factory=list)
    album: str = ""
    album_auto_synced: bool = True
    selected_artwork_id: str | None = None

    duration_seconds: int | None = None
    preview_audio_url: str | None = None

    # Original tags read during analysis (ONLY for smart classification; NEVER exported to MP3)
    original_genres: list[str] = Field(default_factory=list)
    original_language: str | None = None

    # Enriched provider results
    metadata_candidates: list[MetadataSourceCandidate] = Field(default_factory=list)
    artwork_candidates: list[ArtworkCandidate] = Field(default_factory=list)
    suggested_tags: list[TagSuggestion] = Field(default_factory=list)
    selected_tag_ids: list[str] = Field(default_factory=list)
    metadata_provenance: dict[str, str] = Field(default_factory=dict)

    # Download tracking
    download_progress: float = 0.0
    downloaded_file_name: str | None = None
    downloaded_file_path: str | None = None

    @property
    def artists_display(self) -> str:
        return ", ".join(self.artists)


class SessionState(BaseModel):
    """Isolated workspace session holding a playlist/track and its independent queue."""

    session_id: str
    source_url: str
    platform: str
    is_playlist: bool = False
    playlist_title: str | None = None
    notice: str | None = None
    tracks: list[TrackState] = Field(default_factory=list)
    queue_track_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    def get_track(self, track_id: str) -> TrackState | None:
        for track in self.tracks:
            if track.id == track_id:
                return track
        return None
