"""Phase 7 & 8 tests: Strict filename format, 4-frame ID3v2.3 export, single/playlist queue, SSE & ZIP."""

import asyncio
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from mutagen.id3 import COMM, ID3, TCON, TDRC, TLAN, TRCK, TXXX
from PIL import Image

from backend.main import create_app
from backend.services.audio.id3_service import write_strict_id3_v23
from backend.services.downloader.ytdlp_service import (
    DownloadServiceError,
    ExtractedEntry,
    ExtractionSummary,
)
from backend.utils.filename import build_mp3_filename, deduplicate_filename


def _make_dirty_mp3(path: Path) -> Path:
    """Create a valid minimal MP3 with extraneous forbidden ID3 tags (TCON, TLAN, COMM, TDRC, TRCK, TXXX)."""
    path.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 413)
    tags = ID3()
    tags.add(TCON(encoding=3, text=["Reggaeton"]))
    tags.add(TLAN(encoding=3, text=["spa"]))
    tags.add(TDRC(encoding=3, text=["2024"]))
    tags.add(TRCK(encoding=3, text=["3/12"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["Old comment"]))
    tags.add(TXXX(encoding=3, desc="MOOD", text=["Hype"]))
    tags.save(str(path), v2_version=3)
    return path


def _make_cover_jpg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (180, 240, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def test_strict_filename_examples_and_deduplication():
    assert build_mp3_filename("Callaíta", ["Bad Bunny", "Tainy"]) == "callaita_bad_bunny.mp3"
    assert build_mp3_filename("DÁKITI", ["Bad Bunny", "Jhay Cortez"]) == "dakiti_bad_bunny.mp3"
    assert (
        build_mp3_filename("La Noche de Anoche", ["Bad Bunny", "Rosalía"])
        == "la_noche_de_anoche_bad_bunny.mp3"
    )
    assert build_mp3_filename("Song: (Remix)? / #1!", ["Artist/One"]) == "song_remix_1_artist_one.mp3"

    used: set[str] = set()
    assert deduplicate_filename("dakiti_bad_bunny.mp3", used) == "dakiti_bad_bunny.mp3"
    assert deduplicate_filename("dakiti_bad_bunny.mp3", used) == "dakiti_bad_bunny_2.mp3"
    assert deduplicate_filename("dakiti_bad_bunny.mp3", used) == "dakiti_bad_bunny_3.mp3"


def test_write_strict_id3_v23_contains_exclusively_four_frames(tmp_path: Path):
    mp3 = _make_dirty_mp3(tmp_path / "dirty.mp3")
    cover = _make_cover_jpg()

    write_strict_id3_v23(
        mp3,
        title="Dakiti",
        artists=["Bad Bunny", "Jhay Cortez"],
        album="EL ÚLTIMO TOUR DEL MUNDO",
        artwork_bytes=cover,
        artwork_mime="image/jpeg",
    )

    tags = ID3(str(mp3))
    frame_ids = {k.split(":")[0] for k in tags.keys()}
    assert frame_ids == {"TIT2", "TPE1", "TALB", "APIC"}
    assert tags["TIT2"].text == ["Dakiti"]
    assert tags["TPE1"].text == ["Bad Bunny, Jhay Cortez"]
    assert tags["TALB"].text == ["EL ÚLTIMO TOUR DEL MUNDO"]
    apic_frames = tags.getall("APIC")
    assert len(apic_frames) == 1
    assert apic_frames[0].type == 3
    assert apic_frames[0].data == cover
    # Ensure NONE of the forbidden fields exist
    for forbidden in ("TCON", "TLAN", "TDRC", "TRCK", "COMM", "TXXX", "USLT"):
        assert forbidden not in frame_ids


@pytest.mark.asyncio
async def test_playlist_batch_download_error_isolation_and_zip_export():
    app = create_app()
    cover = _make_cover_jpg()

    entries = [
        ExtractedEntry(
            source_id="ok_1",
            url="https://www.youtube.com/watch?v=ok_1",
            title="Callaíta",
            raw_title="Bad Bunny - Callaíta",
            artists=["Bad Bunny", "Tainy"],
            album="Un Verano Sin Ti",
            duration_seconds=250,
            extractor="Youtube",
        ),
        ExtractedEntry(
            source_id="fail_2",
            url="https://www.youtube.com/watch?v=fail_2",
            title="Broken Track",
            raw_title="Broken Track",
            artists=["Nobody"],
            album=None,
            duration_seconds=180,
            extractor="Youtube",
        ),
        ExtractedEntry(
            source_id="ok_3",
            url="https://www.youtube.com/watch?v=ok_3",
            title="Dakiti",
            raw_title="Bad Bunny - Dakiti",
            artists=["Bad Bunny", "Jhay Cortez"],
            album=None,  # Tests Rule 8.1 fallback to title
            duration_seconds=205,
            extractor="Youtube",
        ),
    ]
    summary = ExtractionSummary(
        source_url="https://music.youtube.com/playlist?list=PL_EXPORT",
        is_playlist=True,
        playlist_title="Export Test",
        entries=entries,
    )

    def fake_details(url: str) -> ExtractedEntry:
        return next(e for e in entries if e.url == url)

    def fake_download(url: str, output_dir: Path, file_stem: str, progress_cb=None) -> Path:
        if "fail_2" in url:
            raise DownloadServiceError("Video privado no accesible")
        out = output_dir / f"{file_stem}.mp3"
        _make_dirty_mp3(out)
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
            side_effect=fake_details,
        ),
        patch(
            "backend.services.downloader.ytdlp_service.ytdlp_service.download_audio_mp3",
            side_effect=fake_download,
        ),
        patch(
            "backend.services.metadata.aggregator.search_all_metadata_providers",
            return_value=([], {}, {}),
        ),
        patch(
            "backend.workers.download_manager.fetch_selected_artwork_bytes",
            return_value=(cover, "image/jpeg"),
        ),
    ):
        from backend.utils.url_validator import validate_url

        mock_val.side_effect = lambda u: validate_url(u, resolve_dns=False)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            an = await client.post(
                "/api/v1/analyze",
                json={"url": "https://music.youtube.com/playlist?list=PL_EXPORT"},
            )
            assert an.status_code == 200
            sid = an.json()["session_id"]

            start = await client.post(f"/api/v1/sessions/{sid}/download-playlist")
            assert start.status_code == 200
            job_id = start.json()["job_id"]

            # Poll job until completion (runs quickly with mocked yt-dlp)
            final_job = None
            for _ in range(50):
                st = await client.get(f"/api/v1/jobs/{job_id}")
                final_job = st.json()
                if final_job["status"] in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.05)

            assert final_job is not None
            assert final_job["status"] == "completed"
            assert final_job["completed_tracks"] == 2
            assert final_job["failed_tracks"] == 1
            assert final_job["zip_ready"] is True

            # Verify individual MP3 delivery
            first_file = next(f for f in final_job["files"] if f["file_name"] == "callaita_bad_bunny.mp3")
            mp3_resp = await client.get(first_file["download_url"])
            assert mp3_resp.status_code == 200
            assert mp3_resp.headers["content-type"] == "audio/mpeg"

            # Verify ZIP archive contents and strict 4-frame ID3 inside the ZIP
            zip_resp = await client.get(final_job["zip_download_url"])
            assert zip_resp.status_code == 200
            with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
                names = set(zf.namelist())
                assert names == {"callaita_bad_bunny.mp3", "dakiti_bad_bunny.mp3"}
                # Inspect Dakiti inside ZIP: album should have fallen back to title ("Dakiti")
                dakiti_bytes = zf.read("dakiti_bad_bunny.mp3")
                dakiti_tags = ID3(io.BytesIO(dakiti_bytes))
                assert {k.split(":")[0] for k in dakiti_tags.keys()} == {"TIT2", "TPE1", "TALB", "APIC"}
                assert dakiti_tags["TALB"].text == ["Dakiti"]
                assert dakiti_tags["TPE1"].text == ["Bad Bunny, Jhay Cortez"]
