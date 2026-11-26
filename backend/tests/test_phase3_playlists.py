"""Phase 3 tests: Playlist analysis, lazy loading, album fallback rule, and independent queue."""

from unittest.mock import patch

import httpx
import pytest

from backend.main import create_app
from backend.services.downloader.ytdlp_service import ExtractedEntry, ExtractionSummary


def _mock_playlist_summary(count: int = 8) -> ExtractionSummary:
    entries = [
        ExtractedEntry(
            source_id=f"vid_{i}",
            url=f"https://www.youtube.com/watch?v=vid_{i}",
            title=f"Canción {i + 1}",
            raw_title=f"Artista {i + 1} - Canción {i + 1}",
            artists=[f"Artista {i + 1}"],
            album=None,
            duration_seconds=180 + i * 10,
            thumbnail_url=f"https://i.ytimg.com/vi/vid_{i}/maxresdefault.jpg",
            extractor="Youtube",
        )
        for i in range(count)
    ]
    return ExtractionSummary(
        source_url="https://music.youtube.com/playlist?list=PLTEST123",
        is_playlist=True,
        playlist_title="Playlist de Prueba",
        entries=entries,
        extractor="YoutubeTab",
    )


@pytest.mark.asyncio
async def test_playlist_analyze_lazy_loads_only_first_track():
    app = create_app()
    processed_urls: list[str] = []

    def fake_details(url: str) -> ExtractedEntry:
        processed_urls.append(url)
        idx = int(url.rsplit("_", 1)[-1])
        return ExtractedEntry(
            source_id=f"vid_{idx}",
            url=url,
            title=f"Canción {idx + 1}",
            raw_title=f"Artista {idx + 1} - Canción {idx + 1}",
            artists=[f"Artista {idx + 1}"],
            album=None,
            duration_seconds=200 + idx,
            thumbnail_url=f"https://i.ytimg.com/vi/vid_{idx}/hqdefault.jpg",
            extractor="Youtube",
        )

    with (
        patch("backend.api.sessions.validate_url") as mock_val,
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_url",
            return_value=_mock_playlist_summary(8),
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_track_details",
            side_effect=fake_details,
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/analyze",
                json={"url": "https://music.youtube.com/playlist?list=PLTEST123"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["is_playlist"] is True
            assert data["total_tracks"] == 8
            assert data["processed_tracks"] == 1
            assert len(processed_urls) == 1
            assert data["tracks"][0]["status"] == "ready"
            assert all(t["status"] == "pending" for t in data["tracks"][1:])

            # Lazy-load track 3 on demand
            sid = data["session_id"]
            t3_id = data["tracks"][2]["id"]
            r3 = await client.post(f"/api/v1/sessions/{sid}/tracks/{t3_id}/process")
            assert r3.status_code == 200
            assert r3.json()["status"] == "ready"
            assert len(processed_urls) == 2

            # Calling process again uses cache (does not re-fetch)
            r3_cached = await client.post(f"/api/v1/sessions/{sid}/tracks/{t3_id}/process")
            assert r3_cached.status_code == 200
            assert len(processed_urls) == 2


@pytest.mark.asyncio
async def test_album_auto_sync_and_independent_queue():
    app = create_app()
    single = _mock_playlist_summary(2)

    with (
        patch("backend.api.sessions.validate_url") as mock_val,
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_url",
            return_value=single,
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_track_details",
            return_value=single.entries[0],
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/analyze",
                json={"url": "https://music.youtube.com/playlist?list=PLTEST123"},
            )
            data = resp.json()
            sid = data["session_id"]
            t0 = data["tracks"][0]

            # Rule 8.1: Initially album == title and auto-synced
            assert t0["album"] == "Canción 1"
            assert t0["album_auto_synced"] is True

            # Updating title updates album automatically
            r_title = await client.patch(
                f"/api/v1/sessions/{sid}/tracks/{t0['id']}/metadata",
                json={"title": "Callaíta", "artists_text": "Bad Bunny, Tainy"},
            )
            assert r_title.status_code == 200
            body = r_title.json()
            assert body["title"] == "Callaíta"
            assert body["album"] == "Callaíta"
            assert body["album_auto_synced"] is True
            assert body["artists"] == ["Bad Bunny", "Tainy"]
            assert body["artists_display"] == "Bad Bunny, Tainy"

            # Manually editing album breaks auto-sync
            r_alb = await client.patch(
                f"/api/v1/sessions/{sid}/tracks/{t0['id']}/metadata",
                json={"album": "Un Verano Sin Ti"},
            )
            assert r_alb.json()["album"] == "Un Verano Sin Ti"
            assert r_alb.json()["album_auto_synced"] is False

            # Subsequent title edit does NOT overwrite manual album
            r_title2 = await client.patch(
                f"/api/v1/sessions/{sid}/tracks/{t0['id']}/metadata",
                json={"title": "Callaita (Edited)"},
            )
            assert r_title2.json()["album"] == "Un Verano Sin Ti"

            # Rule 17: Removing from queue keeps original playlist intact
            r_del = await client.delete(f"/api/v1/sessions/{sid}/queue/{t0['id']}")
            assert r_del.status_code == 200
            qdata = r_del.json()
            assert qdata["total_tracks"] == 2
            assert t0["id"] not in qdata["queue_track_ids"]
            assert qdata["tracks"][0]["in_queue"] is False

            # Clearing the entire queue empties queue_track_ids while keeping all tracks intact
            r_clear = await client.delete(f"/api/v1/sessions/{sid}/queue")
            assert r_clear.status_code == 200
            cdata = r_clear.json()
            assert cdata["total_tracks"] == 2
            assert cdata["queue_track_ids"] == []
            assert all(t["in_queue"] is False for t in cdata["tracks"])
