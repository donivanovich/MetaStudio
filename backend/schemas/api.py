"""Typed request and response schemas for the REST API."""

from pydantic import BaseModel, Field

from backend.models.domain import (
    ArtworkCandidate,
    MetadataSourceCandidate,
    TagSuggestion,
    TrackStatus,
)


class AnalyzeRequest(BaseModel):
    """Submit a single track or playlist URL for analysis."""

    url: str = Field(..., min_length=5, max_length=2048)


class TrackResponse(BaseModel):
    """Frontend-friendly track payload (never exposes server filesystem paths)."""

    id: str
    index: int
    source_id: str
    source_url: str
    platform: str
    audio_downloadable: bool
    status: TrackStatus
    error_message: str | None = None

    title: str
    artists: list[str]
    artists_display: str
    album: str
    album_auto_synced: bool
    selected_artwork_id: str | None = None
    selected_artwork_url: str | None = None

    duration_seconds: int | None = None
    preview_audio_url: str | None = None

    metadata_candidates: list[MetadataSourceCandidate] = Field(default_factory=list)
    artwork_candidates: list[ArtworkCandidate] = Field(default_factory=list)
    suggested_tags: list[TagSuggestion] = Field(default_factory=list)
    selected_tag_ids: list[str] = Field(default_factory=list)
    metadata_provenance: dict[str, str] = Field(default_factory=dict)

    in_queue: bool = True
    download_progress: float = 0.0
    downloaded_file_name: str | None = None
    download_url: str | None = None


class SessionResponse(BaseModel):
    """Full session state returned after analysis or session query."""

    session_id: str
    source_url: str
    platform: str
    is_playlist: bool
    playlist_title: str | None = None
    notice: str | None = None
    total_tracks: int
    processed_tracks: int
    queue_track_ids: list[str]
    tracks: list[TrackResponse]


class UpdateMetadataRequest(BaseModel):
    """Edit ONLY the four permitted metadata fields: title, artists, album, artwork."""

    title: str | None = Field(default=None, max_length=300)
    artists: list[str] | None = None
    artists_text: str | None = Field(default=None, max_length=400)
    album: str | None = Field(default=None, max_length=300)
    selected_artwork_id: str | None = None


class ApplyCandidateRequest(BaseModel):
    """Apply a specific metadata provider candidate to the editable fields."""

    source: str
    fields: list[str] | None = None  # optional subset: ["title", "artists", "album"]


class UpdateTagsRequest(BaseModel):
    """Replace selected tag IDs for a track (stored separately from MP3 ID3)."""

    tag_ids: list[str] = Field(default_factory=list)


class DownloadJobResponse(BaseModel):
    """Status snapshot for a single-track or full-playlist download job."""

    job_id: str
    session_id: str
    job_type: str  # "single" | "playlist"
    status: str  # "queued" | "running" | "completed" | "failed" | "cancelled"
    total_tracks: int
    completed_tracks: int
    failed_tracks: int
    pending_tracks: int
    current_track_id: str | None = None
    current_track_title: str | None = None
    current_track_progress: float = 0.0
    zip_ready: bool = False
    zip_download_url: str | None = None
    files: list[dict[str, str]] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)
