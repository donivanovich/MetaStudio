"""FFmpeg discovery, startup verification, and safe path resolution."""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from backend.config.settings import get_settings


@dataclass(frozen=True)
class FFmpegStatus:
    """Verification report for the FFmpeg binary."""

    available: bool
    path: str | None = None
    version: str | None = None
    source: str | None = None
    error: str | None = None


def _resolve_ffmpeg_candidate() -> tuple[str | None, str | None]:
    """Resolve FFmpeg binary from env, PATH, or bundled imageio-ffmpeg."""
    settings = get_settings()
    if settings.ffmpeg_path:
        candidate = Path(settings.ffmpeg_path)
        if candidate.is_file():
            return str(candidate), "env"
        return str(candidate), "env_missing"

    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg, "system_path"

    try:
        import imageio_ffmpeg  # type: ignore

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).is_file():
            return bundled, "imageio_ffmpeg"
    except Exception:
        pass

    return None, None


def verify_ffmpeg() -> FFmpegStatus:
    """Check that FFmpeg exists and responds to `-version` safely."""
    exe_path, source = _resolve_ffmpeg_candidate()
    if not exe_path:
        return FFmpegStatus(
            available=False,
            error=(
                "FFmpeg no encontrado. Instala FFmpeg en el PATH del sistema, "
                "configura FFMPEG_PATH en .env o instala imageio-ffmpeg."
            ),
        )

    if source == "env_missing":
        return FFmpegStatus(
            available=False,
            path=exe_path,
            source="env",
            error=f"La ruta configurada en FFMPEG_PATH no existe: {exe_path}",
        )

    try:
        proc = subprocess.run(
            [exe_path, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )
        if proc.returncode != 0:
            return FFmpegStatus(
                available=False,
                path=exe_path,
                source=source,
                error=f"FFmpeg devolvió código {proc.returncode}: {proc.stderr.strip()[:200]}",
            )
        first_line = (proc.stdout or "").splitlines()[0].strip() if proc.stdout else "unknown"
        return FFmpegStatus(
            available=True,
            path=exe_path,
            version=first_line,
            source=source,
        )
    except Exception as exc:
        return FFmpegStatus(
            available=False,
            path=exe_path,
            source=source,
            error=f"Error verificando FFmpeg: {exc}",
        )


def get_ffmpeg_executable() -> str | None:
    """Return the verified FFmpeg executable path if available."""
    status = verify_ffmpeg()
    return status.path if status.available else None
