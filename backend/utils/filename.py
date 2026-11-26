"""Strict MP3 filename formatter: `nombrecancion_primerartista.mp3`."""

import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def _slugify_segment(text: str) -> str:
    """Normalize Unicode to lowercase ASCII slug with single underscore separators."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    replaced = _NON_ALNUM_RE.sub("_", ascii_only)
    collapsed = _MULTI_UNDERSCORE_RE.sub("_", replaced).strip("_")
    return collapsed


def build_mp3_filename(title: str, artists: list[str]) -> str:
    """
    Build the mandatory export filename format: `nombrecancion_primerartista.mp3`.

    Examples:
    - ("Callaíta", ["Bad Bunny", "Tainy"]) -> "callaita_bad_bunny.mp3"
    - ("DÁKITI", ["Bad Bunny", "Jhay Cortez"]) -> "dakiti_bad_bunny.mp3"
    - ("La Noche de Anoche", ["Bad Bunny", "Rosalía"]) -> "la_noche_de_anoche_bad_bunny.mp3"
    """
    song_slug = _slugify_segment(title) or "track"
    first_artist = artists[0] if artists else ""
    artist_slug = _slugify_segment(first_artist) or "unknown_artist"
    # Keep filename safely under OS path limits
    stem = f"{song_slug[:80]}_{artist_slug[:60]}".strip("_")
    return f"{stem}.mp3"


def deduplicate_filename(filename: str, used_names: set[str]) -> str:
    """Prevent overwriting duplicate MP3 filenames without mutating internal ID3 tags."""
    if filename not in used_names:
        used_names.add(filename)
        return filename

    stem = filename[:-4] if filename.lower().endswith(".mp3") else filename
    counter = 2
    while True:
        candidate = f"{stem}_{counter}.mp3"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1
