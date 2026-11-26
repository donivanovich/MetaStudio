"""Phase 5 tests: Versioned tag catalog, MP3 TCON/TLAN reading, smart mood/language inference."""

from pathlib import Path

import httpx
import pytest
from mutagen.id3 import ID3, TCON, TLAN

from backend.main import create_app
from backend.services.classification.catalog import CATALOG_VERSION, tag_catalog
from backend.services.classification.classifier import classify_track


def _create_tagged_dummy_mp3(tmp_path: Path, genre: str | None = None, lang: str | None = None) -> Path:
    mp3 = tmp_path / "sample.mp3"
    # Minimal valid MPEG audio frame header bytes so Mutagen can attach ID3 cleanly
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 413)
    tags = ID3()
    if genre:
        tags.add(TCON(encoding=3, text=[genre]))
    if lang:
        tags.add(TLAN(encoding=3, text=[lang]))
    tags.save(str(mp3), v2_version=3)
    return mp3


def test_catalog_contains_required_languages_and_moods():
    exported = tag_catalog.export_catalog()
    assert exported["catalog_version"] == CATALOG_VERSION
    lang_ids = {t["id"] for t in exported["languages"]}
    mood_ids = {t["id"] for t in exported["moods"]}
    assert {"lang.es", "lang.en", "lang.fr", "lang.pt", "lang.it", "lang.de", "lang.ja", "lang.ko", "lang.instrumental", "lang.unknown"}.issubset(lang_ids)
    assert {"mood.sad", "mood.hype", "mood.chill", "mood.happy", "mood.romantic", "mood.energetic", "mood.melancholic", "mood.aggressive", "mood.relaxed", "mood.dark", "mood.nostalgic"}.issubset(mood_ids)


def test_classification_uses_original_mp3_tcon_and_tlan(tmp_path: Path):
    mp3 = _create_tagged_dummy_mp3(tmp_path, genre="Sad Trap", lang="spa")
    suggestions = classify_track(
        title="Midnight Song",
        artists=["Artist X"],
        original_genres=[],
        original_language=None,
        mp3_path=mp3,
    )
    ids = [s.tag_id for s in suggestions]
    assert "lang.es" in ids
    assert "mood.sad" in ids
    assert "mood.melancholic" in ids
    # Ensure provenance cites the original MP3 frames
    lang_sug = next(s for s in suggestions if s.tag_id == "lang.es")
    mood_sug = next(s for s in suggestions if s.tag_id == "mood.sad")
    assert lang_sug.source == "mp3_tlan"
    assert mood_sug.source == "mp3_tcon"


def test_genre_to_mood_associations():
    lofi = classify_track(title="Rainy Study", artists=["Beats"], original_genres=["Lo-fi"])
    assert {"mood.chill", "mood.relaxed"}.issubset({s.tag_id for s in lofi})

    reggaeton = classify_track(title="Dakiti", artists=["Bad Bunny"], original_genres=["Reggaeton"])
    assert "mood.hype" in {s.tag_id for s in reggaeton}
    assert "lang.es" in {s.tag_id for s in reggaeton}


def test_no_information_does_not_hallucinate_tags():
    empty = classify_track(
        title="Track 01",
        artists=["Unknown"],
        original_genres=[],
        original_language=None,
    )
    assert empty == []


@pytest.mark.asyncio
async def test_tags_catalog_api_endpoint():
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/tags/catalog")
        assert resp.status_code == 200
        body = resp.json()
        assert body["catalog_version"] == CATALOG_VERSION
        assert len(body["languages"]) >= 10
        assert len(body["moods"]) >= 11
