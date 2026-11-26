"""Phase 4 tests: Multi-factor scoring, provider parsers, Pillow artwork validation & upload."""

import io
from unittest.mock import patch

import httpx
import pytest
from PIL import Image

from backend.main import create_app
from backend.models.domain import MetadataSourceCandidate
from backend.services.artwork.artwork_service import ArtworkValidationError, process_image_bytes
from backend.services.downloader.ytdlp_service import ExtractedEntry, ExtractionSummary
from backend.services.metadata.providers import (
    parse_deezer_payload,
    parse_discogs_payload,
    parse_itunes_payload,
    parse_musicbrainz_payload,
)
from backend.services.metadata.scoring import rank_and_combine_candidates


def test_scoring_picks_best_match_not_first():
    wrong_first = MetadataSourceCandidate(
        source="Deezer",
        title="Completely Unrelated Remix",
        artists=["DJ Random"],
        album="Club Hits 2020",
        duration_seconds=410,
        confidence=0.0,
    )
    accurate_second = MetadataSourceCandidate(
        source="MusicBrainz",
        title="La Noche de Anoche",
        artists=["Bad Bunny", "Rosalía"],
        album="EL ÚLTIMO TOUR DEL MUNDO",
        duration_seconds=203,
        confidence=0.0,
    )
    confirming_third = MetadataSourceCandidate(
        source="Apple Music",
        title="La Noche de Anoche",
        artists=["Bad Bunny", "Rosalía"],
        album="EL ÚLTIMO TOUR DEL MUNDO",
        duration_seconds=204,
        confidence=0.0,
    )

    ranked, provenance, combined = rank_and_combine_candidates(
        query_title="La Noche de Anoche",
        query_artists=["Bad Bunny"],
        query_duration=203,
        raw_candidates=[wrong_first, accurate_second, confirming_third],
    )

    assert ranked[0].source in {"MusicBrainz", "Apple Music"}
    assert ranked[0].confidence > 0.85
    assert ranked[-1].source == "Deezer"
    assert combined["title"] == "La Noche de Anoche"
    assert combined["artists"] == ["Bad Bunny", "Rosalía"]
    assert combined["album"] == "EL ÚLTIMO TOUR DEL MUNDO"
    assert "title" in provenance and "artists" in provenance and "album" in provenance


def test_provider_parsers_preserve_structure():
    mb = parse_musicbrainz_payload(
        {
            "recordings": [
                {
                    "id": "rec-1",
                    "title": "Dakiti",
                    "length": 205000,
                    "artist-credit": [
                        {"name": "Bad Bunny"},
                        {"name": "Jhay Cortez"},
                    ],
                    "releases": [{"id": "rel-1", "title": "EL ÚLTIMO TOUR DEL MUNDO"}],
                    "tags": [{"name": "reggaeton"}],
                }
            ]
        }
    )
    assert len(mb) == 1
    assert mb[0].artists == ["Bad Bunny", "Jhay Cortez"]
    assert mb[0].album == "EL ÚLTIMO TOUR DEL MUNDO"
    assert mb[0].genres == ["reggaeton"]

    dz = parse_deezer_payload(
        {
            "data": [
                {
                    "id": 101,
                    "title": "Dakiti",
                    "duration": 205,
                    "preview": "https://cdns-preview.dzcdn.net/sample.mp3",
                    "artist": {"name": "Bad Bunny"},
                    "album": {"title": "EL ÚLTIMO TOUR DEL MUNDO", "cover_xl": "https://img/1000.jpg"},
                }
            ]
        }
    )
    assert dz[0].preview_url == "https://cdns-preview.dzcdn.net/sample.mp3"
    assert dz[0].artwork_url == "https://img/1000.jpg"

    it = parse_itunes_payload(
        {
            "results": [
                {
                    "trackId": 999,
                    "trackName": "Dakiti",
                    "artistName": "Bad Bunny & Jhayco",
                    "collectionName": "EL ÚLTIMO TOUR DEL MUNDO",
                    "trackTimeMillis": 205000,
                    "primaryGenreName": "Urbano latino",
                    "artworkUrl100": "https://is1.mzstatic.com/image/100x100bb.jpg",
                    "previewUrl": "https://audio-ssl.itunes.apple.com/sample.m4a",
                }
            ]
        }
    )
    assert it[0].artwork_url == "https://is1.mzstatic.com/image/1400x1400bb.jpg"
    assert it[0].genres == ["Urbano latino"]

    dg = parse_discogs_payload(
        {"results": [{"id": 55, "title": "Bad Bunny - Dakiti", "genre": ["Latin"], "style": ["Reggaeton"]}]}
    )
    assert dg[0].artists == ["Bad Bunny"]
    assert "Reggaeton" in dg[0].genres


def test_pillow_artwork_validation_and_rejection():
    buf = io.BytesIO()
    Image.new("RGBA", (800, 800), (120, 220, 40, 255)).save(buf, format="PNG")
    processed, w, h, mime = process_image_bytes(buf.getvalue())
    assert mime == "image/jpeg"
    assert (w, h) == (800, 800)
    assert len(processed) > 100

    with pytest.raises(ArtworkValidationError):
        process_image_bytes(b"not an image at all")


@pytest.mark.asyncio
async def test_custom_artwork_upload_and_session_serving():
    app = create_app()
    entry = ExtractedEntry(
        source_id="v1",
        url="https://www.youtube.com/watch?v=v1",
        title="Me Equivoqué",
        raw_title="Fito & Fitipaldis - Me Equivoqué",
        artists=["Fito & Fitipaldis"],
        album="Huyendo Conmigo de Mí",
        duration_seconds=241,
        extractor="Youtube",
    )
    summary = ExtractionSummary(
        source_url=entry.url, is_playlist=False, playlist_title=None, entries=[entry]
    )

    buf = io.BytesIO()
    Image.new("RGB", (500, 500), (40, 90, 180)).save(buf, format="JPEG")
    jpg_bytes = buf.getvalue()

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
            r = await client.post("/api/v1/analyze", json={"url": entry.url})
            sid = r.json()["session_id"]
            tid = r.json()["tracks"][0]["id"]

            up = await client.post(
                f"/api/v1/sessions/{sid}/tracks/{tid}/artwork/upload",
                files={"file": ("cover.jpg", jpg_bytes, "image/jpeg")},
            )
            assert up.status_code == 200
            tdata = up.json()
            assert tdata["selected_artwork_url"].startswith(f"/api/v1/sessions/{sid}/artwork/")

            img_resp = await client.get(tdata["selected_artwork_url"])
            assert img_resp.status_code == 200
            assert img_resp.headers["content-type"] == "image/jpeg"

            # Reject fake image upload
            bad_up = await client.post(
                f"/api/v1/sessions/{sid}/tracks/{tid}/artwork/upload",
                files={"file": ("evil.jpg", b"<script>alert(1)</script>", "image/jpeg")},
            )
            assert bad_up.status_code == 400
