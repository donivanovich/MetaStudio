"""Tests for collaborating artist extraction, feat. relocation, and version qualifier formatting."""

import httpx
import pytest

from backend.models.domain import (
    ArtworkCandidate,
    MetadataSourceCandidate,
    SessionState,
    TrackState,
)
from backend.services.downloader.ytdlp_service import (
    _normalize_info_to_entry,
    clean_track_title_and_artists,
)
from backend.services.metadata.aggregator import enrich_track_metadata_and_artwork
from backend.services.metadata.providers import (
    parse_deezer_payload,
    parse_itunes_payload,
    search_deezer,
)
from backend.services.metadata.scoring import rank_and_combine_candidates
from backend.utils.metadata_normalizer import (
    normalize_album_name,
    normalize_title_and_artists,
    split_artist_string,
)


def test_user_example_remix_and_feat_moved_to_artists():
    title, artists = normalize_title_and_artists(
        "LA VERDAD (remix) feat. No se quien",
        ["Artista Principal"],
    )
    assert title == "LA VERDAD remix"
    assert artists == ["Artista Principal", "No se quien"]


def test_feat_before_remix_and_inside_mixed_parentheses():
    title1, artists1 = normalize_title_and_artists(
        "LA VERDAD feat. No se quien (remix)",
        ["Artista Principal"],
    )
    assert title1 == "LA VERDAD remix"
    assert artists1 == ["Artista Principal", "No se quien"]

    title2, artists2 = normalize_title_and_artists(
        "LA VERDAD (Remix feat. Artista 2, Artista 3 & Artista 4)",
        ["Artista 1"],
    )
    assert title2 == "LA VERDAD Remix"
    assert artists2 == ["Artista 1", "Artista 2", "Artista 3", "Artista 4"]


def test_split_artist_string_preserves_names_ending_in_x_and_handles_collaborators():
    assert split_artist_string("Alex Rose & Dalex") == ["Alex Rose", "Dalex"]
    assert split_artist_string("Bad Bunny x Jhayco x Mora") == ["Bad Bunny", "Jhayco", "Mora"]
    assert split_artist_string("Karol G, Feid y Quevedo") == ["Karol G", "Feid", "Quevedo"]
    assert split_artist_string("AC/DC") == ["AC/DC"]


def test_normal_titles_with_with_or_con_are_not_corrupted():
    title1, artists1 = normalize_title_and_artists("Con Altura", ["Rosalía", "J Balvin"])
    assert title1 == "Con Altura"
    assert artists1 == ["Rosalía", "J Balvin"]

    title2, artists2 = normalize_title_and_artists("Dancing With Myself", ["Billy Idol"])
    assert title2 == "Dancing With Myself"
    assert artists2 == ["Billy Idol"]


def test_ytdlp_clean_extracts_all_collaborators_even_when_single_uploader_present():
    title, artists = clean_track_title_and_artists(
        "Artista 1 x Artista 2 - LA VERDAD (remix) feat. No se quien [Video Oficial]",
        uploader="Artista 1 - Topic",
        artist_field="Artista 1",
    )
    assert title == "LA VERDAD remix"
    assert artists == ["Artista 1", "Artista 2", "No se quien"]


def test_ytdlp_normalize_mines_collaborators_from_video_title_when_track_is_short():
    entry = _normalize_info_to_entry(
        {
            "id": "vid999",
            "track": "LA VERDAD (remix)",
            "title": "Artista 1 x Artista 2 - LA VERDAD (remix) feat. No se quien (Official Video)",
            "artist": "Artista 1",
            "duration": 210,
            "ie_key": "Youtube",
        },
        fallback_url="https://www.youtube.com/watch?v=vid999",
    )
    assert entry.title == "LA VERDAD remix"
    assert entry.artists == ["Artista 1", "Artista 2", "No se quien"]


def test_itunes_and_deezer_parsers_extract_all_collaborators():
    it = parse_itunes_payload(
        {
            "results": [
                {
                    "trackId": 123,
                    "trackName": "LA VERDAD (Remix) [feat. Mora & Sech]",
                    "artistName": "Karol G, Feid & Quevedo",
                    "collectionName": "LA VERDAD - Single",
                    "trackTimeMillis": 215000,
                }
            ]
        }
    )
    assert it[0].title == "LA VERDAD Remix"
    assert it[0].artists == ["Karol G", "Feid", "Quevedo", "Mora", "Sech"]

    dz = parse_deezer_payload(
        {
            "data": [
                {
                    "id": 456,
                    "title": "LA VERDAD (Remix) (feat. Sech)",
                    "duration": 215,
                    "artist": {"name": "Karol G"},
                    "contributors": [
                        {"name": "Karol G"},
                        {"name": "Feid"},
                        {"name": "Quevedo"},
                    ],
                    "album": {"title": "LA VERDAD"},
                }
            ]
        }
    )
    assert dz[0].title == "LA VERDAD Remix"
    assert dz[0].artists == ["Karol G", "Feid", "Quevedo", "Sech"]


@pytest.mark.asyncio
async def test_search_deezer_fetches_full_track_contributors():
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 777,
                            "title": "LA VERDAD (remix)",
                            "duration": 200,
                            "artist": {"name": "Artista 1"},
                            "album": {"title": "Album X"},
                        }
                    ]
                },
            )
        if request.url.path == "/track/777":
            return httpx.Response(
                200,
                json={
                    "id": 777,
                    "contributors": [
                        {"name": "Artista 1"},
                        {"name": "Artista 2"},
                        {"name": "Artista 3"},
                    ],
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(_handler)) as client:
        candidates = await search_deezer(client, "LA VERDAD remix", ["Artista 1"])

    assert len(candidates) == 1
    assert candidates[0].title == "LA VERDAD remix"
    assert candidates[0].artists == ["Artista 1", "Artista 2", "Artista 3"]


def test_cross_source_scoring_merges_all_collaborating_artists():
    c1 = MetadataSourceCandidate(
        source="Deezer",
        title="LA VERDAD (remix)",
        artists=["Artista 1", "Artista 2"],
        album="Album Real",
        duration_seconds=210,
        confidence=0.0,
    )
    c2 = MetadataSourceCandidate(
        source="Apple Music",
        title="LA VERDAD (remix) feat. Artista 3",
        artists=["Artista 1", "Artista 2"],
        album="Album Real",
        duration_seconds=210,
        confidence=0.0,
    )
    c3 = MetadataSourceCandidate(
        source="MusicBrainz",
        title="LA VERDAD remix",
        artists=["Artista 1", "Artista 4"],
        album="Album Real",
        duration_seconds=210,
        confidence=0.0,
    )

    _ranked, _prov, combined = rank_and_combine_candidates(
        query_title="LA VERDAD remix",
        query_artists=["Artista 1", "Artista 2"],
        query_duration=210,
        raw_candidates=[c1, c2, c3],
    )
    assert combined["title"] == "LA VERDAD remix"
    assert combined["artists"] == ["Artista 1", "Artista 2", "Artista 3", "Artista 4"]


@pytest.mark.asyncio
async def test_aggregator_preserves_raw_title_feat_artists_when_provider_omits_them(monkeypatch):
    async def _fake_search(title, artists, duration_seconds=None):
        cand = MetadataSourceCandidate(
            source="Deezer",
            title="LA VERDAD remix",
            artists=["Artista 1"],
            album="Album Real",
            duration_seconds=210,
            confidence=0.92,
        )
        return (
            [cand],
            {"title": "Deezer", "artists": "Deezer", "album": "Deezer"},
            {"title": "LA VERDAD remix", "artists": ["Artista 1"], "album": "Album Real"},
        )

    monkeypatch.setattr(
        "backend.services.metadata.aggregator.search_all_metadata_providers",
        _fake_search,
    )

    track = TrackState(
        id="trk-1",
        index=0,
        source_id="vid-1",
        source_url="https://www.youtube.com/watch?v=vid-1",
        platform="youtube",
        raw_title="Artista 1 x Artista 2 - LA VERDAD (remix) feat. No se quien",
        title="LA VERDAD remix",
        artists=["Artista 1", "Artista 2", "No se quien"],
        album="LA VERDAD remix",
    )
    session = SessionState(
        session_id="11111111-1111-4111-8111-111111111111",
        source_url=track.source_url,
        platform="youtube",
        tracks=[track],
        queue_track_ids=[track.id],
    )

    await enrich_track_metadata_and_artwork(session, track)
    assert track.title == "LA VERDAD remix"
    assert track.artists == ["Artista 1", "Artista 2", "No se quien"]


def test_album_normalization_strips_single_and_feat_and_unwraps_remix():
    assert normalize_album_name("LA VERDAD (Remix) [feat. Mora] - Single") == "LA VERDAD Remix"
    assert normalize_album_name("EL ÚLTIMO TOUR DEL MUNDO") == "EL ÚLTIMO TOUR DEL MUNDO"
    assert normalize_album_name("   ") is None


@pytest.mark.asyncio
async def test_youtube_jpeg_artwork_is_default_first_and_origin_candidate_is_preserved(monkeypatch):
    async def _fake_search(title, artists, duration_seconds=None):
        sp = MetadataSourceCandidate(
            source="Spotify",
            title="LA VERDAD remix",
            artists=["Artista 1", "Artista 2"],
            album="LA VERDAD remix",
            duration_seconds=210,
            confidence=0.95,
            artwork_url="https://i.scdn.co/image/spotify_640.jpg",
        )
        am = MetadataSourceCandidate(
            source="Apple Music",
            title="LA VERDAD remix",
            artists=["Artista 1", "Artista 2"],
            album="Album Oficial",
            duration_seconds=210,
            confidence=0.94,
            artwork_url="https://is1.mzstatic.com/image/1400x1400bb.jpg",
        )
        return (
            [sp, am],
            {"title": "Spotify", "artists": "Spotify", "album": "Apple Music"},
            {"title": "LA VERDAD remix", "artists": ["Artista 1", "Artista 2"], "album": "Album Oficial"},
        )

    monkeypatch.setattr(
        "backend.services.metadata.aggregator.search_all_metadata_providers",
        _fake_search,
    )

    yt_art = ArtworkCandidate(
        id="art-yt1",
        source="YouTube",
        url="https://i.ytimg.com/vi/abc/maxresdefault.jpg",
        format="jpeg",
        selected=True,
    )
    track = TrackState(
        id="trk-yt",
        index=0,
        source_id="abc",
        source_url="https://www.youtube.com/watch?v=abc",
        platform="youtube",
        raw_title="LA VERDAD (remix) feat. Artista 2",
        title="LA VERDAD remix",
        artists=["Artista 1", "Artista 2"],
        album="LA VERDAD remix",
        album_auto_synced=True,
        selected_artwork_id=yt_art.id,
        artwork_candidates=[yt_art],
    )
    session = SessionState(
        session_id="22222222-2222-4222-8222-222222222222",
        source_url=track.source_url,
        platform="youtube",
        tracks=[track],
        queue_track_ids=[track.id],
    )

    await enrich_track_metadata_and_artwork(session, track)
    assert track.artwork_candidates[0].source == "YouTube"
    assert track.artwork_candidates[0].format == "jpeg"
    assert track.selected_artwork_id == "art-yt1"
    assert track.artwork_candidates[0].selected is True
    assert {c.source for c in track.metadata_candidates} == {"Spotify", "Apple Music", "YouTube"}
