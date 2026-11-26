"""Mutagen ID3 metadata reader (for smart classification) and strict 4-frame ID3v2.3 writer."""

from dataclasses import dataclass, field
from pathlib import Path

from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError

# Strictly permitted frames in exported MP3 files (Rule 15)
ALLOWED_EXPORT_FRAMES = {"TIT2", "TPE1", "TALB", "APIC"}


@dataclass(frozen=True)
class OriginalID3Metadata:
    """Original ID3 tags inspected solely as classification input (never copied blindly to export)."""

    genres: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    title: str | None = None
    artists: list[str] = field(default_factory=list)
    album: str | None = None


def read_original_id3_metadata(mp3_path: Path) -> OriginalID3Metadata:
    """Read original TCON (genre), TLAN (language), and descriptive frames from an MP3 file."""
    if not mp3_path.is_file():
        return OriginalID3Metadata()

    try:
        tags = ID3(str(mp3_path))
    except ID3NoHeaderError:
        return OriginalID3Metadata()

    genres: list[str] = []
    for frame_key in ("TCON",):
        frame = tags.get(frame_key)
        if frame and getattr(frame, "text", None):
            for item in frame.text:
                text = str(item).strip()
                if text:
                    genres.append(text)

    languages: list[str] = []
    tlan = tags.get("TLAN")
    if tlan and getattr(tlan, "text", None):
        for item in tlan.text:
            text = str(item).strip()
            if text:
                languages.append(text)

    # Also inspect any TXXX language/genre custom tags if present in the source file
    for frame in tags.getall("TXXX"):
        desc = (getattr(frame, "desc", "") or "").strip().lower()
        values = [str(v).strip() for v in (getattr(frame, "text", None) or []) if str(v).strip()]
        if desc in {"language", "lang", "idioma"}:
            languages.extend(values)
        elif desc in {"genre", "style", "mood"}:
            genres.extend(values)

    title = str(tags["TIT2"].text[0]).strip() if "TIT2" in tags and tags["TIT2"].text else None
    album = str(tags["TALB"].text[0]).strip() if "TALB" in tags and tags["TALB"].text else None
    artists: list[str] = []
    if "TPE1" in tags and tags["TPE1"].text:
        for item in tags["TPE1"].text:
            for part in str(item).split(","):
                if part.strip():
                    artists.append(part.strip())

    return OriginalID3Metadata(
        genres=list(dict.fromkeys(genres)),
        languages=list(dict.fromkeys(languages)),
        title=title,
        artists=artists,
        album=album,
    )


def write_strict_id3_v23(
    mp3_path: Path,
    *,
    title: str,
    artists: list[str],
    album: str,
    artwork_bytes: bytes | None = None,
    artwork_mime: str = "image/jpeg",
) -> None:
    """
    Strip ALL existing ID3 frames and write EXCLUSIVELY the 4 permitted ID3v2.3 frames:
    TIT2 (Title), TPE1 (Artists joined by ', '), TALB (Album), APIC (Front Cover).

    ID3v2.3 (UTF-16, encoding=1) is chosen for maximum compatibility across Windows Explorer,
    macOS, iOS, Android, VLC, Rekordbox, and embedded hardware players.
    """
    if not mp3_path.is_file():
        raise FileNotFoundError(f"Archivo MP3 no encontrado: {mp3_path}")

    # Completely remove any pre-existing ID3v1 / ID3v2 frames (TCON, TLAN, COMM, TDRC, etc.)
    try:
        existing = ID3(str(mp3_path))
        existing.delete(str(mp3_path))
    except ID3NoHeaderError:
        pass

    clean_tags = ID3()
    clean_title = (title or "Untitled").strip()
    clean_artists = ", ".join(a.strip() for a in artists if a and a.strip())
    clean_album = (album or clean_title).strip()

    clean_tags.add(TIT2(encoding=1, text=[clean_title]))
    if clean_artists:
        clean_tags.add(TPE1(encoding=1, text=[clean_artists]))
    clean_tags.add(TALB(encoding=1, text=[clean_album]))

    if artwork_bytes:
        clean_tags.add(
            APIC(
                encoding=1,
                mime=artwork_mime or "image/jpeg",
                type=3,  # Front Cover
                desc="Cover",
                data=artwork_bytes,
            )
        )

    # Save strictly as ID3v2.3 and omit legacy ID3v1 (v1=0) so no stale genre/year leaks
    clean_tags.save(str(mp3_path), v1=0, v2_version=3)
