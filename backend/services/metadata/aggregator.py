"""Concurrent metadata aggregator with TTL caching and enrichment hook for TrackProcessor."""

import asyncio
import logging
import uuid

import httpx

from backend.models.domain import (
    ArtworkCandidate,
    MetadataSourceCandidate,
    SessionState,
    TrackState,
)
from backend.services.metadata.providers import (
    search_deezer,
    search_discogs,
    search_itunes,
    search_musicbrainz,
    search_spotify,
)
from backend.services.metadata.scoring import normalize_text, rank_and_combine_candidates
from backend.services.storage.store import session_store
from backend.utils.metadata_normalizer import (
    artist_dedupe_key,
    extract_feat_artists_from_title,
    merge_artist_lists,
    normalize_title_and_artists,
)

logger = logging.getLogger(__name__)

_DEFAULT_ARTWORK_DIMENSIONS: dict[str, tuple[int, int]] = {
    "Spotify": (640, 640),
    "Apple Music": (1400, 1400),
    "Deezer": (1000, 1000),
    "MusicBrainz": (500, 500),
    "Discogs": (600, 600),
    "YouTube Music": (1200, 1200),
    "YouTube": (1280, 720),
}


async def search_all_metadata_providers(
    title: str,
    artists: list[str],
    duration_seconds: int | None = None,
) -> tuple[list[MetadataSourceCandidate], dict[str, str], dict[str, object]]:
    """Query all active providers concurrently, cache results, and return ranked matches."""
    cache_key = f"{normalize_text(title)}::{normalize_text(artists[0] if artists else '')}"
    cached = session_store.metadata_cache.get(cache_key)
    if cached is not None:
        return cached

    raw_candidates: list[MetadataSourceCandidate] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = [
            search_deezer(client, title, artists),
            search_itunes(client, title, artists),
            search_musicbrainz(client, title, artists),
            search_discogs(client, title, artists),
            search_spotify(client, title, artists),
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    for idx, outcome in enumerate(results):
        if isinstance(outcome, Exception):
            logger.debug("Metadata provider #%d unavailable: %s", idx, outcome)
            continue
        raw_candidates.extend(outcome)

    ranked, provenance, combined = rank_and_combine_candidates(
        query_title=title,
        query_artists=artists,
        query_duration=duration_seconds,
        raw_candidates=raw_candidates,
    )
    bundle = (ranked, provenance, combined)
    if ranked:
        session_store.metadata_cache.set(cache_key, bundle)
    return bundle


async def enrich_track_metadata_and_artwork(
    _session: SessionState, track: TrackState
) -> None:
    """TrackProcessor enrichment hook: populates metadata matches, combined fields, artwork, and preview URL."""
    ranked, provenance, combined = await search_all_metadata_providers(
        title=track.title,
        artists=track.artists,
        duration_seconds=track.duration_seconds,
    )
    if not ranked:
        return

    track.metadata_candidates = ranked

    # Auto-fill editable fields ONLY when not manually overridden by the user
    if combined:
        if track.metadata_provenance.get("title") != "manual" and combined.get("title"):
            track.title = str(combined["title"])
            track.metadata_provenance["title"] = provenance.get("title", ranked[0].source)

        if track.metadata_provenance.get("artists") != "manual" and combined.get("artists"):
            provider_artists = list(combined["artists"])  # type: ignore[arg-type]
            # Preserve any explicit `feat.` collaborators from the original title
            # plus verified collaborators from yt-dlp when the primary artist matches
            _, raw_feat_artists = extract_feat_artists_from_title(track.raw_title)
            provider_keys = {artist_dedupe_key(a) for a in provider_artists}
            existing_keys = {artist_dedupe_key(a) for a in track.artists}
            extra_from_track = track.artists if (len(track.artists) > 1 and (provider_keys & existing_keys)) else []
            merged_artists = merge_artist_lists(provider_artists, extra_from_track, raw_feat_artists)
            track.artists = merged_artists
            track.metadata_provenance["artists"] = provenance.get("artists", ranked[0].source)

        if track.metadata_provenance.get("album") != "manual":
            if combined.get("album"):
                track.album = str(combined["album"])
                track.album_auto_synced = False
                track.metadata_provenance["album"] = provenance.get("album", ranked[0].source)
            elif track.album_auto_synced or not track.album:
                track.album = track.title
                track.album_auto_synced = True
                track.metadata_provenance["album"] = "auto_from_title"
    elif track.metadata_provenance.get("title") != "manual":
        # Even if no external providers matched, keep title/artists cleanly normalized
        clean_title, clean_artists = normalize_title_and_artists(
            track.title, track.artists, structured_artists=True
        )
        if clean_title:
            track.title = clean_title
        if track.metadata_provenance.get("artists") != "manual" and clean_artists:
            track.artists = clean_artists

    # Collect genres & authorized preview URL from matched providers
    for cand in ranked:
        if cand.genres:
            track.original_genres = list(dict.fromkeys([*track.original_genres, *cand.genres]))
        if cand.language and not track.original_language:
            track.original_language = cand.language
        # Prefer reliable 30s HTTPS preview (Deezer / Apple Music) for smooth browser playback
        if cand.preview_url and cand.confidence >= 0.65:
            if not track.preview_audio_url or "googlevideo.com" in track.preview_audio_url:
                track.preview_audio_url = cand.preview_url

    # Aggregate distinct artworks from verified matches (only matching editions >= 0.60 confidence)
    existing_urls = {a.url for a in track.artwork_candidates}
    new_artworks: list[ArtworkCandidate] = []
    for cand in ranked:
        if cand.artwork_url and cand.artwork_url not in existing_urls and cand.confidence >= 0.55:
            dims = _DEFAULT_ARTWORK_DIMENSIONS.get(cand.source, (None, None))
            new_artworks.append(
                ArtworkCandidate(
                    id=f"art-{uuid.uuid4().hex[:8]}",
                    source=cand.source,
                    url=cand.artwork_url,
                    width=dims[0],
                    height=dims[1],
                    format="jpeg",
                    is_custom=False,
                    selected=False,
                )
            )
            existing_urls.add(cand.artwork_url)

    # Sort artwork candidates prioritizing highest resolution square covers first
    if new_artworks:
        track.artwork_candidates = new_artworks + track.artwork_candidates
        track.artwork_candidates.sort(
            key=lambda a: (
                a.is_custom,
                (a.width or 0) * (a.height or 0) if (a.width == a.height) else (a.width or 0) * 100,
            ),
            reverse=True,
        )

    # Select best artwork automatically ONLY if user hasn't manually chosen one
    if track.metadata_provenance.get("artwork") != "manual" and track.artwork_candidates:
        best_art = track.artwork_candidates[0]
        for art in track.artwork_candidates:
            art.selected = art.id == best_art.id
        track.selected_artwork_id = best_art.id
        track.metadata_provenance["artwork"] = best_art.source
