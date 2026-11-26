"""On-demand lazy track processor coordinating yt-dlp details, metadata, artwork, and tags."""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from backend.models.domain import (
    ArtworkCandidate,
    SessionState,
    TrackState,
    TrackStatus,
)
from backend.services.downloader.ytdlp_service import (
    DownloadServiceError,
    ExtractedEntry,
    ytdlp_service,
)
from backend.services.storage.store import session_store

logger = logging.getLogger(__name__)

EnrichHook = Callable[[SessionState, TrackState], Awaitable[None]]


class TrackProcessor:
    """Processes a single track on demand (lazy loading) and caches results."""

    def __init__(self) -> None:
        self._enrichment_hooks: list[EnrichHook] = []
        self._locks: dict[str, asyncio.Lock] = {}

    def register_enrichment_hook(self, hook: EnrichHook) -> None:
        """Allow metadata, artwork, and classification phases to attach cleanly."""
        if hook not in self._enrichment_hooks:
            self._enrichment_hooks.append(hook)

    def _get_lock(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def process_track(
        self,
        session: SessionState,
        track: TrackState,
        *,
        force: bool = False,
    ) -> TrackState:
        """Enrich one track on demand. Already-processed tracks are served from cache."""
        if (
            not force
            and track.status in {TrackStatus.READY, TrackStatus.DOWNLOADED}
            and (track.metadata_candidates or track.artwork_candidates or track.duration_seconds)
        ):
            return track

        lock = self._get_lock(f"{session.session_id}:{track.id}")
        async with lock:
            if (
                not force
                and track.status in {TrackStatus.READY, TrackStatus.DOWNLOADED}
                and (track.metadata_candidates or track.artwork_candidates)
            ):
                return track

            track.status = TrackStatus.PROCESSING
            track.error_message = None

            try:
                if track.audio_downloadable:
                    details = await asyncio.to_thread(
                        ytdlp_service.extract_track_details, track.source_url
                    )
                    self._merge_extracted_details(track, details)

                # Run registered enrichment hooks (metadata search, artwork search, smart tagging)
                for hook in self._enrichment_hooks:
                    try:
                        await hook(session, track)
                    except Exception as hook_exc:
                        logger.warning(
                            "Enrichment hook %s failed for track %s: %s",
                            getattr(hook, "__name__", hook),
                            track.id,
                            hook_exc,
                        )

                # Ensure album fallback rule 8.1 is respected
                if not track.album:
                    track.album = track.title
                    track.album_auto_synced = True
                    track.metadata_provenance.setdefault("album", "auto_from_title")

                # Restore any user-persisted tags for this track URL
                persisted = session_store.load_persisted_tags(track.source_url)
                if persisted:
                    track.selected_tag_ids = persisted

                track.status = TrackStatus.READY
            except DownloadServiceError as exc:
                track.status = TrackStatus.ERROR
                track.error_message = str(exc)
            except Exception as exc:
                logger.exception("Unexpected error processing track %s", track.id)
                track.status = TrackStatus.ERROR
                track.error_message = f"Error procesando la canción: {exc}"

            session_store.save_session(session)
            return track

    @staticmethod
    def _merge_extracted_details(track: TrackState, details: ExtractedEntry) -> None:
        """Merge yt-dlp single-track details without overwriting manual user edits."""
        origin_label = (
            "YouTube Music"
            if track.platform == "youtube_music"
            else (
                "YouTube"
                if not details.extractor or details.extractor.lower() == "youtube"
                else details.extractor
            )
        )
        if track.metadata_provenance.get("title") != "manual" and details.title:
            track.title = details.title
            track.metadata_provenance["title"] = origin_label

        if track.metadata_provenance.get("artists") != "manual" and details.artists:
            track.artists = details.artists
            track.metadata_provenance["artists"] = origin_label

        if track.metadata_provenance.get("album") != "manual":
            if details.album:
                track.album = details.album
                track.album_auto_synced = False
                track.metadata_provenance["album"] = origin_label
            elif track.album_auto_synced or not track.album:
                track.album = track.title
                track.album_auto_synced = True
                track.metadata_provenance["album"] = "auto_from_title"

        if details.duration_seconds:
            track.duration_seconds = details.duration_seconds
        if details.preview_audio_url and not track.preview_audio_url:
            track.preview_audio_url = details.preview_audio_url
        if details.original_genres:
            track.original_genres = list(
                dict.fromkeys([*track.original_genres, *details.original_genres])
            )
        if details.original_language and not track.original_language:
            track.original_language = details.original_language

        if details.thumbnail_url:
            source_label = (
                "YouTube Music"
                if track.platform == "youtube_music"
                else (
                    "YouTube"
                    if not details.extractor or details.extractor.lower() == "youtube"
                    else details.extractor
                )
            )
            existing_yt = next(
                (
                    a
                    for a in track.artwork_candidates
                    if not a.is_custom and "youtube" in a.source.lower()
                ),
                None,
            )
            if existing_yt is not None:
                existing_yt.url = details.thumbnail_url
                existing_yt.source = source_label
                existing_yt.format = "jpeg"
            else:
                existing_urls = {a.url for a in track.artwork_candidates}
                if details.thumbnail_url not in existing_urls:
                    art_id = f"art-{uuid.uuid4().hex[:8]}"
                    is_first = len(track.artwork_candidates) == 0
                    track.artwork_candidates.insert(
                        0,
                        ArtworkCandidate(
                            id=art_id,
                            source=source_label,
                            url=details.thumbnail_url,
                            format="jpeg",
                            selected=is_first and track.selected_artwork_id is None,
                        ),
                    )
                    if is_first and track.selected_artwork_id is None:
                        track.selected_artwork_id = art_id
                        track.metadata_provenance.setdefault("artwork", source_label)


track_processor = TrackProcessor()
