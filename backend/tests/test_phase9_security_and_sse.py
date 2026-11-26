"""Phase 9 tests: Session isolation, path traversal blocking, SSE streaming, and DRM honesty."""

import io
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from backend.main import create_app
from backend.services.downloader.ytdlp_service import ExtractedEntry, ExtractionSummary


def _make_jpg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (80, 140, 220)).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_cross_session_isolation_and_path_traversal_blocked():
    app = create_app()
    entry = ExtractedEntry(
        source_id="iso_1",
        url="https://www.youtube.com/watch?v=iso_1",
        title="Track A",
        raw_title="Artist A - Track A",
        artists=["Artist A"],
        album="Album A",
        duration_seconds=180,
        extractor="Youtube",
    )
    summary = ExtractionSummary(
        source_url=entry.url, is_playlist=False, playlist_title=None, entries=[entry]
    )

    with (
        patch("backend.api.sessions.validate_url") as mock_val,
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_url",
            return_value=summary,
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_track_details",
            return_value=entry,
        ),
        patch(
            "backend.services.metadata.aggregator.search_all_metadata_providers",
            return_value=([], {}, {}),
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            s1 = (await client.post("/api/v1/analyze", json={"url": entry.url})).json()
            s2 = (await client.post("/api/v1/analyze", json={"url": entry.url})).json()

            up = await client.post(
                f"/api/v1/sessions/{s1['session_id']}/tracks/{s1['tracks'][0]['id']}/artwork/upload",
                files={"file": ("cover.jpg", _make_jpg(), "image/jpeg")},
            )
            assert up.status_code == 200
            art_url: str = up.json()["selected_artwork_url"]
            filename = art_url.rsplit("/", 1)[-1]

            # Session 2 MUST NOT access Session 1's artwork
            cross = await client.get(f"/api/v1/sessions/{s2['session_id']}/artwork/{filename}")
            assert cross.status_code == 404

            # Path traversal MUST be rejected
            trav = await client.get(f"/api/v1/sessions/{s1['session_id']}/artwork/..%2F..%2F.env")
            assert trav.status_code == 404


@pytest.mark.asyncio
async def test_drm_url_refuses_fake_download_honestly():
    app = create_app()
    with (
        patch("backend.api.sessions.validate_url") as mock_val,
        patch(
            "backend.services.metadata.aggregator.search_all_metadata_providers",
            return_value=([], {}, {}),
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            an = await client.post(
                "/api/v1/analyze",
                json={"url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"},
            )
            assert an.status_code == 200
            data = an.json()
            assert data["tracks"][0]["audio_downloadable"] is False
            assert data["notice"] is not None

            dl = await client.post(
                f"/api/v1/sessions/{data['session_id']}/tracks/{data['tracks'][0]['id']}/download"
            )
            assert dl.status_code == 400
            assert "DRM" in dl.json()["detail"]


@pytest.mark.asyncio
async def test_sse_stream_delivers_completion_event_and_persists_tags():
    app = create_app()
    entry = ExtractedEntry(
        source_id="sse_1",
        url="https://www.youtube.com/watch?v=sse_1",
        title="La Noche de Anoche",
        raw_title="Bad Bunny - La Noche de Anoche",
        artists=["Bad Bunny", "Rosalía"],
        album="EL ÚLTIMO TOUR DEL MUNDO",
        duration_seconds=203,
        original_genres=["Reggaeton"],
        extractor="Youtube",
    )
    summary = ExtractionSummary(
        source_url=entry.url, is_playlist=False, playlist_title=None, entries=[entry]
    )

    def fake_dl(_url: str, output_dir: Path, file_stem: str, progress_cb=None) -> Path:
        out = output_dir / f"{file_stem}.mp3"
        out.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 413)
        if progress_cb:
            progress_cb(90.0, "tagging")
        return out

    with (
        patch("backend.api.sessions.validate_url") as mock_val,
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_url",
            return_value=summary,
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.extract_track_details",
            return_value=entry,
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.download_audio_mp3",
            side_effect=fake_dl,
        ),
        patch(
            "backend.services.metadata.aggregator.search_all_metadata_providers",
            return_value=([], {}, {}),
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            an = await client.post("/api/v1/analyze", json={"url": entry.url})
            sid = an.json()["session_id"]
            tid = an.json()["tracks"][0]["id"]

            # Persist user tag selection independently
            put_tags = await client.put(
                f"/api/v1/sessions/{sid}/tracks/{tid}/tags",
                json={"tag_ids": ["lang.es", "mood.hype", "mood.romantic"]},
            )
            assert put_tags.status_code == 200
            assert put_tags.json()["selected_tag_ids"] == ["lang.es", "mood.hype", "mood.romantic"]

            # Start single download and consume SSE stream
            dl = await client.post(f"/api/v1/sessions/{sid}/tracks/{tid}/download")
            job_id = dl.json()["job_id"]

            events: list[dict] = []
            async with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as stream:
                assert stream.status_code == 200
                assert "text/event-stream" in stream.headers["content-type"]
                async for line in stream.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

            assert len(events) >= 1
            assert events[-1]["status"] == "completed"
            assert events[-1]["files"][0]["file_name"] == "la_noche_de_anoche_bad_bunny.mp3"
