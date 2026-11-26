"""Phase 2 tests: FFmpeg verification, URL validation/SSRF, yt-dlp normalization, health endpoint."""

import httpx
import pytest

from backend.main import create_app
from backend.services.audio.ffmpeg_service import verify_ffmpeg
from backend.services.downloader.ytdlp_service import (
    _normalize_info_to_entry,
    clean_track_title_and_artists,
)
from backend.utils.url_validator import URLValidationError, validate_url


def test_ffmpeg_is_available_and_verified():
    status = verify_ffmpeg()
    assert status.available is True, f"FFmpeg expected available, got: {status.error}"
    assert status.path is not None
    assert status.version is not None


def test_validate_youtube_single_and_playlist_urls():
    single = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ", resolve_dns=False)
    assert single.platform == "youtube"
    assert single.is_playlist_hint is False
    assert single.audio_downloadable is True

    yt_music_pl = validate_url(
        "https://music.youtube.com/watch?v=HjF3E2zGNkg&list=RDoU6uUEwZ8FM",
        resolve_dns=False,
    )
    assert yt_music_pl.platform == "youtube_music"
    assert yt_music_pl.is_playlist_hint is True
    assert yt_music_pl.audio_downloadable is True


def test_validate_drm_platforms_marked_metadata_only():
    dz = validate_url("https://www.deezer.com/track/12345", resolve_dns=False)
    assert dz.platform == "deezer"
    assert dz.audio_downloadable is False
    assert dz.metadata_only is True
    assert dz.notice is not None

    am = validate_url("https://music.apple.com/es/album/example/12345", resolve_dns=False)
    assert am.platform == "apple_music"
    assert am.audio_downloadable is False
    assert am.metadata_only is True


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "ftp://example.com/song.mp3",
        "file:///etc/passwd",
        "http://localhost:8000/admin",
        "http://127.0.0.1/internal",
        "http://192.168.1.10/secret",
        "http://169.254.169.254/latest/meta-data/",
        "https://user:pass@youtube.com/watch?v=123",
        "https://youtube.com/watch?v=123 bad",
    ],
)
def test_ssrf_and_invalid_urls_rejected(bad_url: str):
    with pytest.raises(URLValidationError):
        validate_url(bad_url, resolve_dns=False)


def test_clean_track_title_and_artists():
    title, artists = clean_track_title_and_artists(
        "Bad Bunny - La Noche de Anoche (feat. Rosalía) [Official Video]",
        uploader="Bad Bunny - Topic",
    )
    assert title == "La Noche de Anoche"
    assert artists == ["Bad Bunny", "Rosalía"]


def test_normalize_flat_playlist_entry():
    entry = _normalize_info_to_entry(
        {
            "id": "abc123XYZ",
            "title": "Fito & Fitipaldis - Me Equivoqué (Videoclip Oficial)",
            "duration": 241,
            "ie_key": "Youtube",
        },
        fallback_url="https://music.youtube.com/playlist?list=PL123",
    )
    assert entry.url == "https://www.youtube.com/watch?v=abc123XYZ"
    assert entry.title == "Me Equivoqué"
    assert entry.duration_seconds == 241


@pytest.mark.asyncio
async def test_health_endpoint():
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["ffmpeg"]["available"] is True
        assert body["providers"]["musicbrainz"] is True
        assert body["providers"]["deezer"] is True
        assert body["providers"]["itunes"] is True
