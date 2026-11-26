"""Centralized track title normalization, feat. extraction, and collaborating artist parsing."""

from __future__ import annotations

import re
import unicodedata

# Video/audio platform noise tags to remove from titles
_TITLE_NOISE_RE = re.compile(
    r"\s*[\(\[]"
    r"(?:official\s*(?:music\s*)?(?:video|audio|lyric\s*video|visualizer)|"
    r"music\s*video|lyric\s*video|lyrics|letra|visualizer|"
    r"audio\s*oficial|video\s*oficial|v[ií]deo\s*oficial|videoclip\s*oficial|"
    r"audio\s*only|video\s*clip|videoclip|hd|4k|hq|explicit|clean)"
    r"[\)\]]",
    flags=re.IGNORECASE,
)

# Parenthesized/bracketed blocks starting with feat/ft/featuring/with/con
_BRACKETED_FEAT_ONLY_RE = re.compile(
    r"\s*[\(\[]\s*(?:feat\.?|ft\.?|featuring|with|con)\s+([^\)\]]+?)[\)\]]",
    flags=re.IGNORECASE,
)

# Mixed parenthesized/bracketed blocks like "(Remix feat. Artist B & Artist C)"
_BRACKETED_INLINE_FEAT_RE = re.compile(
    r"([\(\[])([^\)\]]+?)\s+(?:feat\.?|ft\.?|featuring|with|con)\s+([^\)\]]+?)([\)\]])",
    flags=re.IGNORECASE,
)

# Unparenthesized feat/ft/featuring anywhere in title (stops before brackets or version suffix)
_INLINE_FEAT_RE = re.compile(
    r"(?:^|\s+)(?:feat\.?|ft\.?|featuring)\s+"
    r"([^\(\[\n]+?)"
    r"(?=\s*[\(\[]|\s+[-–—]\s+(?:remix|acoustic|ac[uú]stic[oa]|live|en\s+vivo|extended|radio\s+edit|edit|mix|vip|version|versi[oó]n|slowed|sped\s+up|instrumental|remaster(?:ed)?|demo)\b|$)",
    flags=re.IGNORECASE,
)

# Version qualifiers that should be unwrapped from parentheses/brackets: e.g. "(remix)" -> "remix"
_VERSION_QUALIFIER_HINT_RE = re.compile(
    r"\b(?:remix|rmx|mix|edit|vip|dub|rework|bootleg|flip|mashup|version|versi[oó]n|"
    r"acoustic|ac[uú]stic[oa]|unplugged|live|en\s+vivo|directo|"
    r"sped\s*up|slowed|reverb|nightcore|8d|"
    r"extended|club|radio|original|instrumental|acapella|a\s*capella|"
    r"remaster(?:ed)?|deluxe|bonus|demo|session|cover)\b",
    flags=re.IGNORECASE,
)

_BRACKETED_BLOCK_RE = re.compile(r"\s*([\(\[])([^\)\]]+)([\)\]])")

# Trailing dash version suffix like "LA VERDAD - Remix" -> "LA VERDAD Remix"
_DASH_VERSION_RE = re.compile(
    r"\s+[-–—]\s+((?:[^-–—]*\b(?:remix|rmx|acoustic|ac[uú]stic[oa]|live|en\s+vivo|"
    r"extended\s*(?:mix|version)?|radio\s*edit|club\s*mix|vip|sped\s*up|slowed(?:\s*\+\s*reverb)?|"
    r"instrumental|acapella|unplugged|remaster(?:ed)?|demo)\b[^-–—]*))$",
    flags=re.IGNORECASE,
)

# Split unstructured artist strings safely (NOTE: `x` / `×` / `y` / `with` / `con` require surrounding spaces!)
_ARTIST_SPLIT_RE = re.compile(
    r"(?:\s*[,;&]\s*|\s+(?:feat\.?|ft\.?|featuring|with|con|y|[x×+/])\s+|^(?:feat\.?|ft\.?|featuring)\s+)",
    flags=re.IGNORECASE,
)

_EMPTY_BRACKETS_RE = re.compile(r"\s*[\(\[]\s*[\)\]]")
_MULTI_SPACE_RE = re.compile(r"\s+")
_PUNCT_KEY_RE = re.compile(r"[^\w\s]", flags=re.UNICODE)


def artist_dedupe_key(name: str) -> str:
    """Accent- and case-insensitive key for deduplicating artist names."""
    decomposed = unicodedata.normalize("NFKD", name or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = _PUNCT_KEY_RE.sub(" ", stripped.lower())
    return _MULTI_SPACE_RE.sub(" ", cleaned).strip()


def _has_diacritics(text: str) -> bool:
    return unicodedata.normalize("NFKD", text) != text


def split_artist_string(raw: str) -> list[str]:
    """Split an unstructured artist string (e.g. 'A, B & C' or 'A x B') into clean artist names."""
    if not raw or not raw.strip():
        return []
    parts = _ARTIST_SPLIT_RE.split(raw.strip())
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = part.strip(" \t\r\n-–—,;&/+")
        if not cleaned:
            continue
        key = artist_dedupe_key(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def merge_artist_lists(*artist_lists: list[str]) -> list[str]:
    """Merge multiple artist lists preserving order, avoiding duplicates, and preferring richer spelling."""
    merged: list[str] = []
    key_to_index: dict[str, int] = {}

    for group in artist_lists:
        for raw_artist in group or []:
            if not isinstance(raw_artist, str):
                continue
            cleaned = _MULTI_SPACE_RE.sub(" ", raw_artist).strip(" \t\r\n-–—,;&/+")
            if not cleaned:
                continue
            key = artist_dedupe_key(cleaned)
            if not key:
                continue
            if key in key_to_index:
                idx = key_to_index[key]
                existing = merged[idx]
                # Prefer version with accents (e.g. "Rosalía" over "Rosalia") or proper casing
                if (not _has_diacritics(existing) and _has_diacritics(cleaned)) or (
                    existing.islower() and not cleaned.islower()
                ):
                    merged[idx] = cleaned
            else:
                key_to_index[key] = len(merged)
                merged.append(cleaned)

    return merged


def normalize_structured_artists(artists: list[str]) -> list[str]:
    """Clean a structured artist list without breaking single-entity names containing commas/ampersands,
    while still splitting explicit feat./ft./x collaboration tokens if embedded."""
    expanded: list[str] = []
    for item in artists or []:
        if not isinstance(item, str) or not item.strip():
            continue
        text = item.strip()
        if re.search(r"\b(?:feat\.?|ft\.?|featuring)\b|\s+[x×]\s+", text, flags=re.IGNORECASE):
            expanded.extend(split_artist_string(text))
        else:
            expanded.append(text)
    return merge_artist_lists(expanded)


def extract_feat_artists_from_title(title: str) -> tuple[str, list[str]]:
    """Remove all feat./ft./featuring/with/con clauses from `title` and return `(clean_title, feat_artists)`."""
    if not title:
        return "", []

    cleaned = _TITLE_NOISE_RE.sub("", title.strip())
    extracted: list[str] = []

    # 1. Pure bracketed feat clauses: "(feat. A & B)", "[ft. C]", "(with D)"
    while True:
        match = _BRACKETED_FEAT_ONLY_RE.search(cleaned)
        if not match:
            break
        extracted.extend(split_artist_string(match.group(1)))
        cleaned = (cleaned[: match.start()] + " " + cleaned[match.end() :]).strip()

    # 2. Mixed bracketed clauses: "(Remix feat. A & B)" -> "(Remix)" + artists [A, B]
    while True:
        match = _BRACKETED_INLINE_FEAT_RE.search(cleaned)
        if not match:
            break
        open_b, before_feat, feat_part, close_b = (
            match.group(1),
            match.group(2).strip(" -–—,"),
            match.group(3),
            match.group(4),
        )
        extracted.extend(split_artist_string(feat_part))
        replacement = f"{open_b}{before_feat}{close_b}" if before_feat else ""
        cleaned = (cleaned[: match.start()] + replacement + cleaned[match.end() :]).strip()

    # 3. Unparenthesized feat clauses: "LA VERDAD (remix) feat. No se quien"
    while True:
        match = _INLINE_FEAT_RE.search(cleaned)
        if not match:
            break
        extracted.extend(split_artist_string(match.group(1)))
        cleaned = (cleaned[: match.start()] + " " + cleaned[match.end() :]).strip()

    cleaned = _EMPTY_BRACKETS_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip(" \t\r\n-–—")
    return cleaned, merge_artist_lists(extracted)


def format_version_qualifiers(title: str) -> str:
    """Unwrap parenthesized/bracketed version tags like '(remix)' -> 'remix' without losing casing."""
    if not title:
        return ""

    def _replace_block(match: re.Match[str]) -> str:
        inner = match.group(2).strip()
        if not inner:
            return ""
        if _VERSION_QUALIFIER_HINT_RE.search(inner):
            return f" {inner}"
        return match.group(0)

    formatted = _BRACKETED_BLOCK_RE.sub(_replace_block, title)
    formatted = _DASH_VERSION_RE.sub(lambda m: f" {m.group(1).strip()}", formatted)
    formatted = _MULTI_SPACE_RE.sub(" ", formatted).strip(" \t\r\n-–—")

    # Avoid accidental trailing duplicate token like "LA VERDAD remix remix"
    tokens = formatted.split()
    if len(tokens) >= 2 and tokens[-1].lower() == tokens[-2].lower():
        tokens.pop()
        formatted = " ".join(tokens)

    return formatted


def normalize_title_and_artists(
    title: str,
    artists: list[str] | None = None,
    *,
    structured_artists: bool = True,
) -> tuple[str, list[str]]:
    """Normalize a track title (strip noise, move feat. to artists, unwrap '(remix)' -> 'remix')
    and return `(clean_title, deduplicated_artists)`."""
    base_artists = (
        normalize_structured_artists(artists or [])
        if structured_artists
        else merge_artist_lists(*(split_artist_string(a) for a in (artists or [])))
    )

    no_feat_title, feat_artists = extract_feat_artists_from_title(title or "")
    final_title = format_version_qualifiers(no_feat_title)
    final_artists = merge_artist_lists(base_artists, feat_artists)

    return final_title or (title or "").strip(), final_artists
