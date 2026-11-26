"""URL validation, platform detection, and SSRF protection."""

import ipaddress
import socket
from dataclasses import dataclass
from typing import Literal
from urllib.parse import parse_qs, urlparse

PlatformName = Literal[
    "youtube",
    "youtube_music",
    "soundcloud",
    "bandcamp",
    "apple_music",
    "deezer",
    "other",
]

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "169.254.169.254",
    "0.0.0.0",
}
BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".lan", ".home")


class URLValidationError(ValueError):
    """Raised when a submitted URL fails format or security validation."""


@dataclass(frozen=True)
class ValidatedURL:
    """Result of validating and classifying a user-submitted URL."""

    url: str
    hostname: str
    platform: PlatformName
    is_playlist_hint: bool
    audio_downloadable: bool
    metadata_only: bool
    notice: str | None = None


def _is_forbidden_ip(ip_str: str) -> bool:
    """Return True if an IP belongs to private, loopback, reserved or link-local ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _check_ssrf(hostname: str, resolve_dns: bool = True) -> None:
    """Block internal hostnames and private/loopback IP destinations."""
    lower = hostname.lower().rstrip(".")
    if not lower:
        raise URLValidationError("La URL no contiene un dominio válido.")

    if lower in BLOCKED_HOSTNAMES or lower.endswith(BLOCKED_SUFFIXES):
        raise URLValidationError(
            "Destino bloqueado por seguridad: no se permiten direcciones locales o internas."
        )

    # Check literal IP first (never swallow URLValidationError)
    parsed_ip = None
    try:
        parsed_ip = ipaddress.ip_address(lower)
    except ValueError:
        parsed_ip = None

    if parsed_ip is not None:
        if _is_forbidden_ip(lower):
            raise URLValidationError(
                "Destino bloqueado por seguridad: dirección IP privada o reservada."
            )
        return

    if not resolve_dns:
        return

    try:
        addr_info = socket.getaddrinfo(lower, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise URLValidationError(
            f"No se pudo resolver el dominio '{lower}'. Verifica la URL o tu conexión."
        ) from exc

    for _, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        if _is_forbidden_ip(ip_str):
            raise URLValidationError(
                "Destino bloqueado por seguridad: el dominio resuelve a una red privada."
            )


def detect_platform(parsed_url) -> tuple[PlatformName, bool, bool, bool, str | None]:
    """Identify source platform, playlist hint, and audio vs metadata capability."""
    host = (parsed_url.hostname or "").lower()
    path = (parsed_url.path or "").lower()
    query = parse_qs(parsed_url.query or "")

    if host == "music.youtube.com":
        is_pl = "/playlist" in path or "list" in query
        return ("youtube_music", is_pl, True, False, None)

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        is_pl = "/playlist" in path or "list" in query
        return ("youtube", is_pl, True, False, None)

    if host in {"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com", "on.soundcloud.com"}:
        is_pl = "/sets/" in path
        return ("soundcloud", is_pl, True, False, None)

    if host.endswith(".bandcamp.com") or host == "bandcamp.com":
        is_pl = "/album/" in path
        return ("bandcamp", is_pl, True, False, None)

    if host in {"music.apple.com", "itunes.apple.com"}:
        is_pl = "/playlist/" in path or "/album/" in path
        return (
            "apple_music",
            is_pl,
            False,
            True,
            (
                "Apple Music está protegido con DRM y no permite descarga directa de audio. "
                "Usa su información para metadatos/carátulas y una fuente autorizada para el audio."
            ),
        )

    if host in {"deezer.com", "www.deezer.com", "deezer.page.link"}:
        is_pl = "/playlist/" in path or "/album/" in path
        return (
            "deezer",
            is_pl,
            False,
            True,
            (
                "Deezer no ofrece descarga directa de archivos completos sin DRM. "
                "Se utiliza como proveedor de metadatos, carátulas y previsualizaciones autorizadas."
            ),
        )

    return ("other", "list" in query or "playlist" in path, True, False, None)


def validate_url(raw_url: str, *, resolve_dns: bool = True) -> ValidatedURL:
    """Validate syntax, scheme, SSRF rules and classify a user-provided URL."""
    if not raw_url or not isinstance(raw_url, str):
        raise URLValidationError("Debes introducir una URL válida.")

    cleaned = raw_url.strip()
    if len(cleaned) > MAX_URL_LENGTH:
        raise URLValidationError("La URL excede la longitud máxima permitida.")

    if any(ch.isspace() for ch in cleaned):
        raise URLValidationError("La URL no puede contener espacios en blanco.")

    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise URLValidationError("Solo se permiten URLs con protocolo http o https.")

    if not parsed.netloc or not parsed.hostname:
        raise URLValidationError("La URL debe incluir un dominio válido.")

    if parsed.username or parsed.password:
        raise URLValidationError("No se permiten credenciales embebidas en la URL.")

    _check_ssrf(parsed.hostname, resolve_dns=resolve_dns)

    platform, is_pl, audio_ok, meta_only, notice = detect_platform(parsed)
    return ValidatedURL(
        url=cleaned,
        hostname=parsed.hostname.lower(),
        platform=platform,
        is_playlist_hint=is_pl,
        audio_downloadable=audio_ok,
        metadata_only=meta_only,
        notice=notice,
    )
