"""Official music metadata provider adapters (MusicBrainz, Deezer, iTunes, Discogs)."""

import asyncio
import logging
import time
from typing import Any

import httpx

from backend.config.settings import get_settings
from backend.models.domain import MetadataSourceCandidate
from backend.utils.metadata_normalizer import (
    merge_artist_lists,
    normalize_album_name,
    normalize_title_and_artists,
    split_artist_string,
)

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(8.0, connect=5.0)
_DEEZER_DETAIL_TIMEOUT = httpx.Timeout(4.0, connect=3.0)
_mb_lock = asyncio.Lock()
_mb_last_call: float = 0.0


def _build_query(title: str, artists: list[str]) -> str:
    artist_part = artists[0] if artists else ""
    return f"{artist_part} {title}".strip()


def parse_deezer_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse Deezer Public Search API JSON payload into normalized candidates."""
    results: list[MetadataSourceCandidate] = []
    for item in (data.get("data") or [])[:5]:
        if not isinstance(item, dict):
            continue
        raw_title = str(item.get("title") or "").strip()
        artist_obj = item.get("artist") or {}
        artist_name = str(artist_obj.get("name") or "").strip()

        raw_artists: list[str] = []
        contributors = item.get("contributors")
        if isinstance(contributors, list):
            for contrib in contributors:
                if isinstance(contrib, dict) and contrib.get("name"):
                    raw_artists.append(str(contrib["name"]).strip())
        if artist_name:
            raw_artists = merge_artist_lists([artist_name], raw_artists)

        album_obj = item.get("album") or {}
        album_title = normalize_album_name(str(album_obj.get("title") or "").strip() or None)
        artwork = (
            album_obj.get("cover_xl")
            or album_obj.get("cover_big")
            or album_obj.get("cover_medium")
        )
        duration = int(item["duration"]) if item.get("duration") else None
        if not raw_title:
            continue

        title, artists = normalize_title_and_artists(
            raw_title, raw_artists, structured_artists=True
        )
        results.append(
            MetadataSourceCandidate(
                source="Deezer",
                title=title,
                artists=artists,
                album=album_title,
                duration_seconds=duration,
                confidence=0.0,
                external_id=str(item.get("id") or ""),
                preview_url=item.get("preview") or None,
                artwork_url=artwork,
            )
        )
    return results


def parse_itunes_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse iTunes / Apple Music Search API JSON payload into normalized candidates."""
    results: list[MetadataSourceCandidate] = []
    for item in (data.get("results") or [])[:5]:
        if not isinstance(item, dict):
            continue
        raw_title = str(item.get("trackName") or "").strip()
        artist = str(item.get("artistName") or "").strip()
        album = normalize_album_name(str(item.get("collectionName") or "").strip() or None)
        ms = item.get("trackTimeMillis")
        duration = int(round(ms / 1000)) if isinstance(ms, (int, float)) and ms > 0 else None
        genre = str(item.get("primaryGenreName") or "").strip()
        art_raw = str(item.get("artworkUrl100") or "")
        artwork = (
            art_raw.replace("100x100bb", "1400x1400bb") if "100x100bb" in art_raw else art_raw or None
        )
        if not raw_title:
            continue

        split_artists = split_artist_string(artist) if artist else []
        title, artists = normalize_title_and_artists(
            raw_title, split_artists or ([artist] if artist else []), structured_artists=True
        )
        results.append(
            MetadataSourceCandidate(
                source="Apple Music",
                title=title,
                artists=artists,
                album=album,
                duration_seconds=duration,
                confidence=0.0,
                external_id=str(item.get("trackId") or ""),
                genres=[genre] if genre else [],
                preview_url=item.get("previewUrl") or None,
                artwork_url=artwork,
            )
        )
    return results


def parse_musicbrainz_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse MusicBrainz recording search payload with structured artist credits and Cover Art Archive URL."""
    results: list[MetadataSourceCandidate] = []
    for rec in (data.get("recordings") or [])[:5]:
        if not isinstance(rec, dict):
            continue
        raw_title = str(rec.get("title") or "").strip()
        if not raw_title:
            continue

        # Preserve individual artist entities (avoid splitting commas inside single artist names)
        raw_artists: list[str] = []
        for credit in rec.get("artist-credit") or []:
            if isinstance(credit, dict):
                name = credit.get("name") or (credit.get("artist") or {}).get("name")
                if isinstance(name, str) and name.strip():
                    raw_artists.append(name.strip())

        title, artists = normalize_title_and_artists(
            raw_title, raw_artists, structured_artists=True
        )

        releases = rec.get("releases") or []
        album = None
        artwork_url = None
        if releases and isinstance(releases[0], dict):
            album = normalize_album_name(str(releases[0].get("title") or "").strip() or None)
            release_id = releases[0].get("id")
            if release_id:
                artwork_url = f"https://coverartarchive.org/release/{release_id}/front-500"

        length_ms = rec.get("length")
        duration = int(round(length_ms / 1000)) if isinstance(length_ms, (int, float)) and length_ms > 0 else None
        genres = [
            str(tag.get("name")).strip()
            for tag in (rec.get("tags") or [])[:6]
            if isinstance(tag, dict) and tag.get("name")
        ]

        results.append(
            MetadataSourceCandidate(
                source="MusicBrainz",
                title=title,
                artists=artists,
                album=album,
                duration_seconds=duration,
                confidence=0.0,
                external_id=str(rec.get("id") or ""),
                genres=genres,
                artwork_url=artwork_url,
            )
        )
    return results


def parse_discogs_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse Discogs database search payload."""
    results: list[MetadataSourceCandidate] = []
    for item in (data.get("results") or [])[:4]:
        if not isinstance(item, dict):
            continue
        raw_title = str(item.get("title") or "").strip()
        if not raw_title:
            continue
        if " - " in raw_title:
            artist_part, title_part = raw_title.split(" - ", 1)
            raw_artists = split_artist_string(artist_part)
            track_title_raw = title_part.strip()
        else:
            raw_artists = []
            track_title_raw = raw_title

        title, artists = normalize_title_and_artists(
            track_title_raw, raw_artists, structured_artists=True
        )

        genres = [
            str(g).strip()
            for g in [*(item.get("genre") or []), *(item.get("style") or [])]
            if isinstance(g, str) and g.strip()
        ]
        cover = item.get("cover_image")
        if isinstance(cover, str) and "spacer.gif" in cover:
            cover = None

        results.append(
            MetadataSourceCandidate(
                source="Discogs",
                title=title,
                artists=artists,
                album=title,
                duration_seconds=None,
                confidence=0.0,
                external_id=str(item.get("id") or ""),
                genres=genres,
                artwork_url=cover,
            )
        )
    return results


async def _fetch_deezer_track_contributors(
    client: httpx.AsyncClient, track_id: str
) -> list[str]:
    """Fetch full contributor list from Deezer `/track/{id}` (missing from `/search` results)."""
    if not track_id:
        return []
    try:
        resp = await client.get(
            f"https://api.deezer.com/track/{track_id}",
            timeout=_DEEZER_DETAIL_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json()
        contributors = payload.get("contributors")
        if not isinstance(contributors, list):
            return []
        return [
            str(c.get("name")).strip()
            for c in contributors
            if isinstance(c, dict) and c.get("name")
        ]
    except Exception:
        return []


async def search_deezer(
    client: httpx.AsyncClient, title: str, artists: list[str]
) -> list[MetadataSourceCandidate]:
    query = _build_query(title, artists)
    if not query:
        return []
    resp = await client.get(
        "https://api.deezer.com/search",
        params={"q": query, "limit": 5},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    candidates = parse_deezer_payload(resp.json())

    # Enrich top 3 Deezer candidates with full `/track/{id}` contributors so collaborating artists are never lost
    top_slice = candidates[:3]
    if top_slice:
        contrib_lists = await asyncio.gather(
            *(_fetch_deezer_track_contributors(client, c.external_id or "") for c in top_slice),
            return_exceptions=True,
        )
        for idx, contribs in enumerate(contrib_lists):
            if isinstance(contribs, list) and contribs:
                candidates[idx] = candidates[idx].model_copy(
                    update={"artists": merge_artist_lists(contribs, candidates[idx].artists)}
                )

    return candidates


async def search_itunes(
    client: httpx.AsyncClient, title: str, artists: list[str]
) -> list[MetadataSourceCandidate]:
    query = _build_query(title, artists)
    if not query:
        return []
    resp = await client.get(
        "https://itunes.apple.com/search",
        params={"term": query, "media": "music", "entity": "song", "limit": 5},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return parse_itunes_payload(resp.json())


async def search_musicbrainz(
    client: httpx.AsyncClient, title: str, artists: list[str]
) -> list[MetadataSourceCandidate]:
    global _mb_last_call
    settings = get_settings()
    if not title:
        return []

    safe_title = title.replace('"', "").strip()
    mb_query = f'recording:"{safe_title}"'
    if artists:
        safe_artist = artists[0].replace('"', "").strip()
        if safe_artist:
            mb_query += f' AND artist:"{safe_artist}"'

    # Respect MusicBrainz 1 req/sec rate limit politely
    async with _mb_lock:
        elapsed = time.monotonic() - _mb_last_call
        if elapsed < 1.05:
            await asyncio.sleep(1.05 - elapsed)
        _mb_last_call = time.monotonic()

    resp = await client.get(
        "https://musicbrainz.org/ws/2/recording/",
        params={"query": mb_query, "fmt": "json", "limit": 5},
        headers={"User-Agent": settings.musicbrainz_user_agent},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return parse_musicbrainz_payload(resp.json())


async def search_discogs(
    client: httpx.AsyncClient, title: str, artists: list[str]
) -> list[MetadataSourceCandidate]:
    settings = get_settings()
    if not settings.discogs_token:
        return []
    query = _build_query(title, artists)
    if not query:
        return []
    resp = await client.get(
        "https://api.discogs.com/database/search",
        params={"q": query, "type": "release", "per_page": 4},
        headers={
            "Authorization": f"Discogs token={settings.discogs_token}",
            "User-Agent": settings.musicbrainz_user_agent,
        },
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return parse_discogs_payload(resp.json())
