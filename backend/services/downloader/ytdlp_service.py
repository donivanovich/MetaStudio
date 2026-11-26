"""yt-dlp Python API integration for lightweight playlist extraction and MP3 downloads."""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yt_dlp

from backend.config.settings import get_settings
from backend.services.audio.ffmpeg_service import get_ffmpeg_executable
from backend.utils.metadata_normalizer import (
    artist_dedupe_key,
    extract_feat_artists_from_title,
    merge_artist_lists,
    normalize_album_name,
    normalize_structured_artists,
    normalize_title_and_artists,
    split_artist_string,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None]


class DownloadServiceError(RuntimeError):
    """Raised when yt-dlp extraction or audio download fails."""


@dataclass
class ExtractedEntry:
    """Lightweight representation of a single track entry from yt-dlp."""

    source_id: str
    url: str
    title: str
    raw_title: str
    artists: list[str] = field(default_factory=list)
    album: str | None = None
    duration_seconds: int | None = None
    thumbnail_url: str | None = None
    extractor: str | None = None
    preview_audio_url: str | None = None
    original_genres: list[str] = field(default_factory=list)
    original_language: str | None = None


@dataclass
class ExtractionSummary:
    """Result of analyzing a single track URL or a playlist URL."""

    source_url: str
    is_playlist: bool
    playlist_title: str | None
    entries: list[ExtractedEntry]
    extractor: str | None = None


def _clean_uploader_name(uploader: str | None) -> str:
    if not uploader:
        return ""
    clean = re.sub(r"\s*-\s*Topic$", "", uploader.strip(), flags=re.IGNORECASE)
    clean = re.sub(r"\s*VEVO$", "", clean, flags=re.IGNORECASE).strip()
    return clean


def clean_track_title_and_artists(
    raw_title: str,
    uploader: str | None = None,
    artist_field: str | None = None,
    artists_list: list[str] | None = None,
) -> tuple[str, list[str]]:
    """Derive clean track title and structured artists list (including all collaborators) from yt-dlp info."""
    cleaned_title = (raw_title or "").strip()

    parsed_artists: list[str] = []
    if artists_list:
        parsed_artists = normalize_structured_artists(artists_list)
    if artist_field:
        parsed_artists = merge_artist_lists(parsed_artists, split_artist_string(artist_field))

    clean_uploader = _clean_uploader_name(uploader)

    # Parse common "Artist A x Artist B - Song Title" YouTube pattern.
    # Also handle when yt-dlp populated only 1 artist/uploader while the video title lists all collaborators!
    if " - " in cleaned_title:
        left, right = cleaned_title.split(" - ", 1)
        left_clean, right_clean = left.strip(), right.strip()
        if left_clean and right_clean:
            left_artists = split_artist_string(left_clean)
            left_keys = {artist_dedupe_key(a) for a in left_artists}
            known_keys = {
                artist_dedupe_key(a)
                for a in [*parsed_artists, *([clean_uploader] if clean_uploader else [])]
                if a
            }
            if not parsed_artists or (left_keys & known_keys):
                # Prefer order from left_artists (usually exact credit order) merged with existing
                parsed_artists = merge_artist_lists(left_artists, parsed_artists)
                cleaned_title = right_clean

    if not parsed_artists and clean_uploader:
        parsed_artists = [clean_uploader]

    # Strip video noise, extract feat./ft./with/con into artists, and unwrap "(remix)" -> "remix"
    final_title, final_artists = normalize_title_and_artists(
        cleaned_title,
        parsed_artists,
        structured_artists=True,
    )

    return final_title or raw_title or "Untitled", final_artists


def _split_artist_string(raw: str) -> list[str]:
    """Split an unstructured artist string into individual names."""
    return split_artist_string(raw)


def _build_entry_url(entry: dict[str, Any], fallback_url: str) -> str:
    """Resolve a playable/extractable URL from a flat or full yt-dlp entry."""
    for key in ("webpage_url", "original_url", "url"):
        val = entry.get(key)
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val
    video_id = entry.get("id")
    ie_key = (entry.get("ie_key") or entry.get("extractor_key") or "").lower()
    if video_id and ("youtube" in ie_key or "youtu" in fallback_url):
        return f"https://www.youtube.com/watch?v={video_id}"
    return fallback_url


def _extract_best_thumbnail(info: dict[str, Any]) -> str | None:
    """Select the highest-resolution thumbnail URL from a yt-dlp info dict."""
    thumbs = info.get("thumbnails")
    if isinstance(thumbs, list) and thumbs:
        scored = []
        for t in thumbs:
            if not isinstance(t, dict) or not t.get("url"):
                continue
            w = int(t.get("width") or 0)
            h = int(t.get("height") or 0)
            scored.append((w * h, t["url"]))
        if scored:
            scored.sort(key=lambda item: item[0], reverse=True)
            return scored[0][1]
    thumb = info.get("thumbnail")
    return thumb if isinstance(thumb, str) else None


def _extract_preview_audio_url(info: dict[str, Any]) -> str | None:
    """Pick an authorized audio-only stream URL if available for in-browser preview."""
    formats = info.get("formats")
    if not isinstance(formats, list):
        return None
    audio_candidates = []
    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        if fmt.get("vcodec") == "none" and fmt.get("acodec") not in (None, "none"):
            ext = (fmt.get("ext") or "").lower()
            url = fmt.get("url")
            if url and ext in {"m4a", "mp3", "webm", "ogg"}:
                abr = float(fmt.get("abr") or 0)
                # Prefer m4a/mp3 for widest HTML5 <audio> browser compatibility
                compat_bonus = 1000 if ext in {"m4a", "mp3"} else 0
                audio_candidates.append((compat_bonus + abr, url))
    if not audio_candidates:
        return None
    audio_candidates.sort(key=lambda item: item[0], reverse=True)
    return audio_candidates[0][1]


def _normalize_info_to_entry(info: dict[str, Any], fallback_url: str) -> ExtractedEntry:
    """Convert a yt-dlp entry dict (flat or full) into an ExtractedEntry."""
    track_field = info.get("track")
    video_title = info.get("title")
    raw_title = str(track_field or video_title or "Untitled")
    artists_raw = info.get("artists") if isinstance(info.get("artists"), list) else None
    artist_str = info.get("artist") or info.get("creator")
    uploader = info.get("uploader") or info.get("channel")
    clean_title, artists = clean_track_title_and_artists(
        raw_title=raw_title,
        uploader=uploader,
        artist_field=artist_str,
        artists_list=artists_raw,
    )

    # When YouTube exposes a short `track` field without collaborators, also mine
    # matching multi-artist prefixes (co-main artists first) and `feat.` from the full video `title`
    if isinstance(track_field, str) and isinstance(video_title, str) and video_title.strip() != track_field.strip():
        if " - " in video_title:
            left_part = video_title.split(" - ", 1)[0].strip()
            left_artists = split_artist_string(left_part)
            known_keys = {artist_dedupe_key(a) for a in artists}
            if len(left_artists) > 1 and ({artist_dedupe_key(a) for a in left_artists} & known_keys):
                artists = merge_artist_lists(artists, left_artists)
        _, title_feats = extract_feat_artists_from_title(video_title)
        if title_feats:
            artists = merge_artist_lists(artists, title_feats)

    duration_raw = info.get("duration")
    duration_seconds = int(duration_raw) if isinstance(duration_raw, (int, float)) and duration_raw > 0 else None

    genres: list[str] = []
    if isinstance(info.get("genre"), str) and info["genre"].strip():
        genres.append(info["genre"].strip())
    if isinstance(info.get("categories"), list):
        for cat in info["categories"]:
            if isinstance(cat, str) and cat.strip() and cat.strip().lower() != "music":
                genres.append(cat.strip())
    if isinstance(info.get("tags"), list):
        for tag in info["tags"][:8]:
            if isinstance(tag, str) and tag.strip():
                genres.append(tag.strip())

    language = info.get("language") if isinstance(info.get("language"), str) else None
    album = (
        normalize_album_name(info["album"])
        if isinstance(info.get("album"), str) and info["album"].strip()
        else None
    )

    return ExtractedEntry(
        source_id=str(info.get("id") or _build_entry_url(info, fallback_url)),
        url=_build_entry_url(info, fallback_url),
        title=clean_title,
        raw_title=raw_title,
        artists=artists,
        album=album,
        duration_seconds=duration_seconds,
        thumbnail_url=_extract_best_thumbnail(info),
        extractor=str(info.get("extractor_key") or info.get("extractor") or info.get("ie_key") or ""),
        preview_audio_url=_extract_preview_audio_url(info),
        original_genres=genres,
        original_language=language,
    )


class YtDlpService:
    """Safe Python wrapper around yt-dlp for extraction and MP3 download."""

    def get_version(self) -> str:
        return getattr(yt_dlp.version, "__version__", "unknown")

    def extract_url(self, url: str) -> ExtractionSummary:
        """Analyze a URL using `extract_flat="in_playlist"` without downloading audio."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            "socket_timeout": 20,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise DownloadServiceError(f"Error extrayendo información de la URL: {exc}") from exc

        if not info or not isinstance(info, dict):
            raise DownloadServiceError(
                "No se pudo obtener información compatible desde la URL proporcionada."
            )

        raw_entries = info.get("entries")
        if raw_entries is not None:
            entries = [
                _normalize_info_to_entry(entry, url)
                for entry in raw_entries
                if isinstance(entry, dict) and (entry.get("id") or entry.get("url"))
            ]
            if not entries:
                raise DownloadServiceError("La playlist no contiene canciones accesibles.")
            return ExtractionSummary(
                source_url=url,
                is_playlist=True,
                playlist_title=str(info.get("title") or "Playlist"),
                entries=entries,
                extractor=str(info.get("extractor_key") or info.get("extractor") or ""),
            )

        entry = _normalize_info_to_entry(info, url)
        return ExtractionSummary(
            source_url=url,
            is_playlist=False,
            playlist_title=None,
            entries=[entry],
            extractor=entry.extractor,
        )

    def extract_track_details(self, url: str) -> ExtractedEntry:
        """Fetch full single-track metadata on demand (used for lazy loading)."""
        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 20,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            raise DownloadServiceError(f"Error obteniendo detalles de la canción: {exc}") from exc

        if not info or not isinstance(info, dict):
            raise DownloadServiceError("No se pudieron obtener los detalles de la canción.")

        return _normalize_info_to_entry(info, url)

    def download_audio_mp3(
        self,
        url: str,
        output_dir: Path,
        file_stem: str,
        progress_cb: ProgressCallback | None = None,
    ) -> Path:
        """Download best available audio and convert to MP3 via FFmpeg."""
        ffmpeg_exe = get_ffmpeg_executable()
        if not ffmpeg_exe:
            raise DownloadServiceError(
                "FFmpeg no está disponible en el servidor. No es posible convertir el audio a MP3."
            )

        settings = get_settings()
        output_dir.mkdir(parents=True, exist_ok=True)
        outtmpl = str(output_dir / f"{file_stem}.%(ext)s")
        expected_mp3 = output_dir / f"{file_stem}.mp3"

        def _hook(status_dict: dict[str, Any]) -> None:
            if not progress_cb:
                return
            state = status_dict.get("status")
            if state == "downloading":
                total = status_dict.get("total_bytes") or status_dict.get("total_bytes_estimate") or 0
                downloaded = status_dict.get("downloaded_bytes") or 0
                pct = (downloaded / total * 80.0) if total > 0 else 25.0
                progress_cb(min(pct, 80.0), "downloading")
            elif state == "finished":
                progress_cb(85.0, "converting")

        ydl_opts: dict[str, Any] = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "outtmpl": outtmpl,
            "ffmpeg_location": ffmpeg_exe,
            "progress_hooks": [_hook],
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(settings.audio_mp3_bitrate),
                }
            ],
            "socket_timeout": 30,
            "retries": 2,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as exc:
            self._cleanup_partials(output_dir, file_stem)
            raise DownloadServiceError(f"Error descargando el audio: {exc}") from exc

        if not expected_mp3.is_file():
            self._cleanup_partials(output_dir, file_stem)
            raise DownloadServiceError("La conversión a MP3 no generó el archivo esperado.")

        if progress_cb:
            progress_cb(92.0, "tagging")
        return expected_mp3

    @staticmethod
    def _cleanup_partials(output_dir: Path, file_stem: str) -> None:
        """Remove incomplete or partial download artifacts on failure."""
        for leftover in output_dir.glob(f"{file_stem}.*"):
            try:
                leftover.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not delete partial artifact: %s", leftover)


ytdlp_service = YtDlpService()
