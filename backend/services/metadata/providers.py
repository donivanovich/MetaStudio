"""Official music metadata provider adapters (MusicBrainz, Deezer, iTunes, Discogs, Spotify)."""

import asyncio
import base64
import logging
import time
from typing import Any

import httpx

from backend.config.settings import get_settings
from backend.models.domain import MetadataSourceCandidate

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(8.0, connect=5.0)
_mb_lock = asyncio.Lock()
_mb_last_call: float = 0.0
_spotify_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


def _build_query(title: str, artists: list[str]) -> str:
    artist_part = artists[0] if artists else ""
    return f"{artist_part} {title}".strip()


def parse_deezer_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse Deezer Public Search API JSON payload into normalized candidates."""
    results: list[MetadataSourceCandidate] = []
    for item in (data.get("data") or [])[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        artist_obj = item.get("artist") or {}
        artist_name = str(artist_obj.get("name") or "").strip()
        album_obj = item.get("album") or {}
        album_title = str(album_obj.get("title") or "").strip() or None
        artwork = (
            album_obj.get("cover_xl")
            or album_obj.get("cover_big")
            or album_obj.get("cover_medium")
        )
        duration = int(item["duration"]) if item.get("duration") else None
        if not title:
            continue
        results.append(
            MetadataSourceCandidate(
                source="Deezer",
                title=title,
                artists=[artist_name] if artist_name else [],
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
        title = str(item.get("trackName") or "").strip()
        artist = str(item.get("artistName") or "").strip()
        album = str(item.get("collectionName") or "").strip() or None
        ms = item.get("trackTimeMillis")
        duration = int(round(ms / 1000)) if isinstance(ms, (int, float)) and ms > 0 else None
        genre = str(item.get("primaryGenreName") or "").strip()
        art_raw = str(item.get("artworkUrl100") or "")
        artwork = (
            art_raw.replace("100x100bb", "1400x1400bb") if "100x100bb" in art_raw else art_raw or None
        )
        if not title:
            continue
        artists = [p.strip() for p in artist.split("&") if p.strip()] if artist else []
        results.append(
            MetadataSourceCandidate(
                source="Apple Music",
                title=title,
                artists=artists or ([artist] if artist else []),
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
        title = str(rec.get("title") or "").strip()
        if not title:
            continue

        # Preserve individual artist entities (Rule 8.2: avoid splitting commas inside single artist names)
        artists: list[str] = []
        for credit in rec.get("artist-credit") or []:
            if isinstance(credit, dict):
                name = credit.get("name") or (credit.get("artist") or {}).get("name")
                if isinstance(name, str) and name.strip():
                    artists.append(name.strip())

        releases = rec.get("releases") or []
        album = None
        artwork_url = None
        if releases and isinstance(releases[0], dict):
            album = str(releases[0].get("title") or "").strip() or None
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
            artists = [artist_part.strip()]
            title = title_part.strip()
        else:
            artists = []
            title = raw_title

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


def parse_spotify_payload(data: dict[str, Any]) -> list[MetadataSourceCandidate]:
    """Parse Spotify Web API track search payload."""
    results: list[MetadataSourceCandidate] = []
    tracks = (data.get("tracks") or {}).get("items") or []
    for item in tracks[:5]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("name") or "").strip()
        if not title:
            continue
        artists = [
            str(a.get("name")).strip()
            for a in (item.get("artists") or [])
            if isinstance(a, dict) and a.get("name")
        ]
        album_obj = item.get("album") or {}
        album = str(album_obj.get("name") or "").strip() or None
        images = album_obj.get("images") or []
        artwork = images[0].get("url") if images and isinstance(images[0], dict) else None
        ms = item.get("duration_ms")
        duration = int(round(ms / 1000)) if isinstance(ms, (int, float)) and ms > 0 else None

        results.append(
            MetadataSourceCandidate(
                source="Spotify",
                title=title,
                artists=artists,
                album=album,
                duration_seconds=duration,
                confidence=0.0,
                external_id=str(item.get("id") or ""),
                preview_url=item.get("preview_url") or None,
                artwork_url=artwork,
            )
        )
    return results


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
    return parse_deezer_payload(resp.json())


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

    mb_query = f'recording:"{title}"'
    if artists:
        mb_query += f' AND artist:"{artists[0]}"'

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


async def _get_spotify_access_token(client: httpx.AsyncClient) -> str | None:
    settings = get_settings()
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        return None
    if _spotify_token_cache["token"] and time.monotonic() < _spotify_token_cache["expires_at"]:
        return str(_spotify_token_cache["token"])

    creds = f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    encoded = base64.b64encode(creds).decode("ascii")
    resp = await client.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        headers={"Authorization": f"Basic {encoded}"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    token = payload.get("access_token")
    expires_in = int(payload.get("expires_in") or 3600)
    if token:
        _spotify_token_cache["token"] = token
        _spotify_token_cache["expires_at"] = time.monotonic() + max(expires_in - 60, 60)
    return token


async def search_spotify(
    client: httpx.AsyncClient, title: str, artists: list[str]
) -> list[MetadataSourceCandidate]:
    token = await _get_spotify_access_token(client)
    if not token:
        return []
    query = _build_query(title, artists)
    if not query:
        return []
    resp = await client.get(
        "https://api.spotify.com/v1/search",
        params={"q": query, "type": "track", "limit": 5},
        headers={"Authorization": f"Bearer {token}"},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return parse_spotify_payload(resp.json())
