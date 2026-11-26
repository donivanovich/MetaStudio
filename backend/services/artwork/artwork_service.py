"""Artwork validation, Pillow processing for ID3 compatibility, and safe remote download."""

import io
import logging
import re
import uuid
from pathlib import Path

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.config.settings import get_settings
from backend.models.domain import ArtworkCandidate, SessionState, TrackState
from backend.services.storage.store import session_store
from backend.utils.url_validator import URLValidationError, validate_url

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_ARTWORK_DIMENSION = 1600
_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9._-]{1,120}$")


class ArtworkValidationError(ValueError):
    """Raised when an uploaded or downloaded artwork fails validation."""


def process_image_bytes(raw_bytes: bytes) -> tuple[bytes, int, int, str]:
    """Validate real image bytes with Pillow and convert to clean ID3-compatible JPEG."""
    settings = get_settings()
    if not raw_bytes:
        raise ArtworkValidationError("El archivo de imagen está vacío.")
    if len(raw_bytes) > settings.max_artwork_upload_bytes:
        raise ArtworkValidationError(
            f"La imagen supera el tamaño máximo permitido ({settings.max_artwork_upload_mb} MB)."
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()
        with Image.open(io.BytesIO(raw_bytes)) as img:
            fmt = (img.format or "").upper()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise ArtworkValidationError(
                    f"Formato de imagen no permitido ({fmt or 'desconocido'}). Usa JPG, PNG o WebP."
                )
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                # Flatten alpha onto clean dark neutral background for universal MP3 player support
                bg = Image.new("RGB", img.size, (18, 18, 22))
                rgba = img.convert("RGBA")
                bg.paste(rgba, mask=rgba.split()[-1])
                img = bg
            elif img.mode == "L":
                img = img.convert("RGB")

            if max(img.size) > MAX_ARTWORK_DIMENSION:
                img.thumbnail((MAX_ARTWORK_DIMENSION, MAX_ARTWORK_DIMENSION), Image.Resampling.LANCZOS)

            width, height = img.size
            out = io.BytesIO()
            img.save(out, format="JPEG", quality=92, optimize=True)
            return out.getvalue(), width, height, "image/jpeg"
    except ArtworkValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ArtworkValidationError("El archivo no es una imagen válida o está corrupto.") from exc


def save_custom_artwork(
    session: SessionState,
    track: TrackState,
    raw_bytes: bytes,
) -> ArtworkCandidate:
    """Validate, process, and save a user-uploaded cover strictly inside the session's temp directory."""
    processed_bytes, width, height, _mime = process_image_bytes(raw_bytes)
    art_dir = session_store.get_session_dir(session.session_id) / "artwork"
    art_dir.mkdir(parents=True, exist_ok=True)

    art_id = f"custom-{uuid.uuid4().hex[:8]}"
    filename = f"{art_id}.jpg"
    file_path = art_dir / filename
    file_path.write_bytes(processed_bytes)

    public_url = f"/api/v1/sessions/{session.session_id}/artwork/{filename}"
    candidate = ArtworkCandidate(
        id=art_id,
        source="Propia",
        url=public_url,
        width=width,
        height=height,
        format="jpeg",
        is_custom=True,
        local_path=str(file_path),
        selected=True,
    )

    for existing in track.artwork_candidates:
        existing.selected = False
    track.artwork_candidates.insert(0, candidate)
    track.selected_artwork_id = art_id
    track.metadata_provenance["artwork"] = "manual"
    session_store.save_session(session)
    return candidate


def resolve_session_artwork_file(session_id: str, filename: str) -> Path | None:
    """Safely locate an uploaded artwork inside a session's isolated directory."""
    if not _SAFE_FILENAME_RE.match(filename):
        return None
    try:
        art_dir = (session_store.get_session_dir(session_id) / "artwork").resolve()
        target = (art_dir / filename).resolve()
        if art_dir not in target.parents:
            return None
        return target if target.is_file() else None
    except ValueError:
        return None


async def fetch_selected_artwork_bytes(
    session_id: str, track: TrackState
) -> tuple[bytes, str] | None:
    """Return validated `(image_bytes, mime_type)` for the track's currently selected artwork."""
    selected = next(
        (a for a in track.artwork_candidates if a.id == track.selected_artwork_id or a.selected),
        track.artwork_candidates[0] if track.artwork_candidates else None,
    )
    if not selected:
        return None

    # Local custom upload
    if selected.local_path:
        path = Path(selected.local_path).resolve()
        session_dir = session_store.get_session_dir(session_id).resolve()
        if session_dir in path.parents and path.is_file():
            return path.read_bytes(), "image/jpeg"

    # Remote artwork URL (SSRF-checked + cached)
    if not selected.url.startswith(("http://", "https://")):
        return None

    cached = session_store.artwork_cache.get(selected.url)
    if cached is not None:
        return cached

    try:
        validate_url(selected.url)
        async with httpx.AsyncClient(follow_redirects=True, timeout=12.0) as client:
            resp = await client.get(selected.url)
            resp.raise_for_status()
            processed, _w, _h, mime = process_image_bytes(resp.content)
            result = (processed, mime)
            session_store.artwork_cache.set(selected.url, result)
            return result
    except (URLValidationError, ArtworkValidationError, httpx.HTTPError) as exc:
        logger.warning("Could not fetch artwork %s: %s", selected.url, exc)
        return None
