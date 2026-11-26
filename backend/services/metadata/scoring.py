"""Multi-factor metadata match scoring and cross-source field combination."""

import re
import unicodedata
from difflib import SequenceMatcher

from backend.models.domain import MetadataSourceCandidate
from backend.utils.metadata_normalizer import (
    merge_artist_lists,
    normalize_title_and_artists,
)

_PUNCT_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Lowercase, strip accents and punctuation for fair fuzzy comparison."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = _PUNCT_RE.sub(" ", stripped.lower())
    return _SPACE_RE.sub(" ", cleaned).strip()


def string_similarity(a: str, b: str) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    tokens_a, tokens_b = set(na.split()), set(nb.split())
    jaccard = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
    return 0.65 * seq + 0.35 * jaccard


def artists_similarity(query_artists: list[str], candidate_artists: list[str]) -> float:
    if not query_artists or not candidate_artists:
        return 0.5  # neutral when source lacked explicit artist
    q_joined = " ".join(query_artists)
    c_joined = " ".join(candidate_artists)
    direct = string_similarity(q_joined, c_joined)
    first = string_similarity(query_artists[0], candidate_artists[0])
    return max(direct, first)


def duration_similarity(query_seconds: int | None, candidate_seconds: int | None) -> float:
    if not query_seconds or not candidate_seconds:
        return 0.5
    diff = abs(query_seconds - candidate_seconds)
    if diff <= 3:
        return 1.0
    if diff <= 8:
        return 0.85
    if diff <= 15:
        return 0.65
    if diff <= 30:
        return 0.4
    return 0.15


def score_candidate(
    *,
    query_title: str,
    query_artists: list[str],
    query_duration: int | None,
    candidate: MetadataSourceCandidate,
    consensus_titles: dict[str, int] | None = None,
    consensus_albums: dict[str, int] | None = None,
) -> float:
    """Compute a 0.0–1.0 reliability score combining title, artists, duration, and cross-source consensus."""
    t_sim = string_similarity(query_title, candidate.title)
    a_sim = artists_similarity(query_artists, candidate.artists)
    d_sim = duration_similarity(query_duration, candidate.duration_seconds)

    score = 0.44 * t_sim + 0.32 * a_sim + 0.16 * d_sim + (0.04 if candidate.album else 0.0)

    # Cross-source agreement bonus (rewards fields confirmed by 2+ independent sources)
    if consensus_titles:
        nt = normalize_text(candidate.title)
        if nt and consensus_titles.get(nt, 0) >= 2:
            score += 0.03
    if consensus_albums and candidate.album:
        na = normalize_text(candidate.album)
        if na and consensus_albums.get(na, 0) >= 2:
            score += 0.03

    return round(min(max(score, 0.0), 0.99), 3)


def rank_and_combine_candidates(
    *,
    query_title: str,
    query_artists: list[str],
    query_duration: int | None,
    raw_candidates: list[MetadataSourceCandidate],
) -> tuple[list[MetadataSourceCandidate], dict[str, str], dict[str, object]]:
    """Score all candidates, keep the best per provider, and synthesize the optimal combined metadata."""
    if not raw_candidates:
        return [], {}, {}

    # Normalize candidates first so feat. artists and "(remix)" -> "remix" are consistent everywhere
    normalized_candidates: list[MetadataSourceCandidate] = []
    for cand in raw_candidates:
        clean_title, clean_artists = normalize_title_and_artists(
            cand.title, cand.artists, structured_artists=True
        )
        normalized_candidates.append(
            cand.model_copy(update={"title": clean_title, "artists": clean_artists})
        )

    # Count cross-source agreement per normalized title and album
    title_sources: dict[str, set[str]] = {}
    album_sources: dict[str, set[str]] = {}
    for cand in normalized_candidates:
        nt = normalize_text(cand.title)
        if nt:
            title_sources.setdefault(nt, set()).add(cand.source)
        if cand.album:
            na = normalize_text(cand.album)
            if na:
                album_sources.setdefault(na, set()).add(cand.source)

    consensus_titles = {k: len(v) for k, v in title_sources.items()}
    consensus_albums = {k: len(v) for k, v in album_sources.items()}

    scored: list[MetadataSourceCandidate] = []
    for cand in normalized_candidates:
        conf = score_candidate(
            query_title=query_title,
            query_artists=query_artists,
            query_duration=query_duration,
            candidate=cand,
            consensus_titles=consensus_titles,
            consensus_albums=consensus_albums,
        )
        scored.append(
            cand.model_copy(
                update={
                    "confidence": conf,
                    "provenance": {
                        "title": cand.source,
                        "artists": cand.source,
                        "album": cand.source if cand.album else "none",
                    },
                }
            )
        )

    # Keep best match per source provider, sorted descending by confidence
    best_by_source: dict[str, MetadataSourceCandidate] = {}
    for cand in sorted(scored, key=lambda c: c.confidence, reverse=True):
        if cand.source not in best_by_source:
            best_by_source[cand.source] = cand

    ranked = sorted(best_by_source.values(), key=lambda c: c.confidence, reverse=True)
    top = ranked[0]

    # Combine fields across high-confidence sources (>= 0.65)
    reliable = [c for c in ranked if c.confidence >= 0.65]
    combined: dict[str, object] = {}
    provenance: dict[str, str] = {}

    if reliable:
        combined["title"] = top.title
        provenance["title"] = top.source

        # Prefer the candidate with the most complete collaborating artists list among matching sources,
        # and merge missing collaborators confirmed by other high-confidence matches of the same track
        same_track_reliable = [
            c
            for c in reliable
            if c.artists
            and c.confidence >= max(0.65, top.confidence - 0.10)
            and string_similarity(top.title, c.title) >= 0.80
        ]
        artist_pool = same_track_reliable or [c for c in reliable if c.artists]
        if artist_pool:
            best_artists_cand = max(
                artist_pool,
                key=lambda c: (len(c.artists), c.confidence),
            )
            merged_artists = list(best_artists_cand.artists)
            contributing_sources = [best_artists_cand.source]
            for other in artist_pool:
                if other.source == best_artists_cand.source:
                    continue
                if other.confidence >= max(0.75, top.confidence - 0.08):
                    before_len = len(merged_artists)
                    merged_artists = merge_artist_lists(merged_artists, other.artists)
                    if len(merged_artists) > before_len:
                        contributing_sources.append(other.source)

            combined["artists"] = merged_artists
            provenance["artists"] = (
                best_artists_cand.source
                if len(contributing_sources) == 1
                else " + ".join(contributing_sources)
            )

        # Prefer an explicit studio album name (non-single) among top high-confidence matches
        norm_title = normalize_text(top.title)
        album_candidates = [c for c in reliable if c.album and c.album.strip()]
        if album_candidates:
            album_cand = max(
                album_candidates,
                key=lambda c: (
                    c.confidence >= top.confidence - 0.05
                    and normalize_text(c.album or "") != norm_title,
                    c.confidence,
                ),
            )
            if album_cand.album:
                combined["album"] = album_cand.album
                provenance["album"] = album_cand.source

    return ranked, provenance, combined
