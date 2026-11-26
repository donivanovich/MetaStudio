# Registro de Desarrollo — MetaStudio Music Downloader

---

## 2026-11-26 — Fase 1: Auditoría inicial, análisis visual y definición de arquitectura

### Implementación
- Auditado el repositorio local `MetaStudio` (rama `main` vacía, remoto `https://github.com/donivanovich/MetaStudio`).
- Verificadas las herramientas del entorno: Python 3.14.7, pip 26.3, Node v24.20.0, npm 11.19.0 (FFmpeg no presente en PATH; se integrará autodetección + soporte `FFMPEG_PATH` + fallback `imageio-ffmpeg`).
- Inspeccionada la referencia visual de Lovable (`https://pixel-perfect-picture-0355.lovable.app`): extraídos la estructura de 3 columnas (`1fr : 1fr : 1.15fr`), paleta OKLCH oscura con acento lima (`--primary`), tokens semánticos de etiquetas (`--lang` cian y `--mood` ámbar), tipografía Geist/Geist Mono, barra de navegación de pistas con estado de procesamiento y footer de acciones.
- Creada la documentación inicial de arquitectura, catálogo de etiquetas versionado, trazabilidad de funcionalidades y archivos de configuración base.

### Archivos creados
- `.gitignore`
- `.env.example`
- `docs/ARCHITECTURE.md`
- `docs/TAG_CATALOG.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Archivos modificados
- Ninguno.

### Motivo del cambio
Establecer la arquitectura cliente-servidor, contratos, decisiones técnicas (ID3v2.3, lazy loading, separación audio/metadatos, seguridad SSRF) y sistema de trazabilidad antes de escribir código de aplicación.

### Validación
- [x] Revisión de estado Git y entorno local.
- [x] Inspección visual y estructural de la referencia de Lovable.
- [x] Documentación base verificada y coherente con los requisitos.

### Resultado
Fase 1 completada correctamente.

### Problemas conocidos
- FFmpeg no está instalado globalmente en el PATH de Windows; se resolverá en Fase 2 mediante autodetección + `imageio-ffmpeg` y se documentará la instalación global.

### Próximo paso
Fase 2: Crear el esqueleto del backend Python (`requirements.txt`, `settings.py`, `ffmpeg_service.py`, `url_validator.py`, `ytdlp_service.py`, `main.py`) y validar cada servicio con pruebas unitarias independientes.

---

## 2026-11-26 — Fase 2: Backend FastAPI, FFmpeg, validación SSRF y servicio yt-dlp

### Implementación
- Creado entorno virtual Python (`backend/.venv`) e instaladas dependencias en `backend/requirements.txt` (`fastapi`, `uvicorn`, `pydantic-settings`, `httpx`, `yt-dlp`, `mutagen`, `Pillow`, `imageio-ffmpeg`, `pytest`, `ruff`).
- Implementada configuración centralizada en `backend/config/settings.py`.
- Implementada autodetección y verificación segura de FFmpeg (`FFMPEG_PATH` → `PATH` → `imageio-ffmpeg`) en `backend/services/audio/ffmpeg_service.py`.
- Implementada validación de URLs, clasificación de plataformas (distinguiendo proveedores de audio descargables frente a plataformas DRM solo metadatos) y bloqueo SSRF en `backend/utils/url_validator.py`.
- Implementado servicio Python `yt-dlp` (`extract_flat="in_playlist"`, extracción bajo demanda y descarga MP3 con limpieza de parciales) en `backend/services/downloader/ytdlp_service.py`.
- Configurada app FastAPI en `backend/main.py` con CORS, middleware ASGI puro de rate-limiting (seguro para SSE) y `/api/v1/health`.

### Archivos creados
- `pyproject.toml`
- `backend/requirements.txt`
- `backend/__init__.py`
- `backend/config/__init__.py`, `backend/config/settings.py`
- `backend/services/__init__.py`, `backend/services/audio/__init__.py`, `backend/services/audio/ffmpeg_service.py`
- `backend/utils/__init__.py`, `backend/utils/url_validator.py`
- `backend/services/downloader/__init__.py`, `backend/services/downloader/ytdlp_service.py`
- `backend/main.py`
- `backend/tests/test_phase2_core.py`

### Archivos modificados
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Motivo del cambio
Establecer el motor Python base verificado con pruebas independientes antes de construir sesiones, playlists y enriquecimiento musical.

### Validación
- [x] Linter (`ruff check backend`: 0 errores).
- [x] Pruebas unitarias (`pytest backend/tests/test_phase2_core.py -v`: 15/15 pasadas).
- [x] Verificación real de FFmpeg (`9.0.2-essentials_build` vía `imageio-ffmpeg`).
- [x] Prueba de `/api/v1/health` y bloqueo SSRF de IPs privadas/locales.

### Resultado
Fase 2 completada y verificada sin errores.

### Problemas conocidos
- Ninguno.

### Próximo paso
Fase 3: Implementar modelos de dominio, esquemas Pydantic, almacén de sesiones aislado con caché, cola independiente y análisis de playlists con lazy loading.

---

## 2026-11-26 — Fase 3: Análisis de playlists, sesiones aisladas y carga diferida (lazy loading)

### Implementación
- Definidos modelos de dominio (`TrackStatus`, `TrackState`, `SessionState`, `MetadataSourceCandidate`, `ArtworkCandidate`, `TagSuggestion`) en `backend/models/domain.py`.
- Definidos contratos REST en `backend/schemas/api.py`.
- Implementado `SessionStore` con aislamiento de directorios por UUID de sesión, caché TTL de metadatos/carátulas, persistencia independiente de etiquetas y reglas estrictas de álbum (fallback + auto-sync reversible) y artistas en `backend/services/storage/store.py`.
- Implementado `TrackProcessor` bajo demanda con bloqueo por canción y arquitectura extensible mediante hooks en `backend/services/track_processor.py`.
- Creados endpoints `/api/v1/analyze`, `/api/v1/sessions/{sid}`, `/api/v1/sessions/{sid}/tracks/{tid}/process`, `PATCH .../metadata`, `POST .../apply-candidate` y gestión independiente de cola (`DELETE/POST .../queue/{tid}`) en `backend/api/sessions.py`.

### Archivos creados
- `backend/models/__init__.py`, `backend/models/domain.py`
- `backend/schemas/__init__.py`, `backend/schemas/api.py`
- `backend/services/storage/__init__.py`, `backend/services/storage/store.py`
- `backend/services/track_processor.py`
- `backend/api/__init__.py`, `backend/api/sessions.py`
- `backend/tests/test_phase3_playlists.py`

### Archivos modificados
- `backend/main.py`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Validación
- [x] Linter (`ruff check backend`: 0 errores).
- [x] Pruebas unitarias (`pytest backend/tests/ -v`: 17/17 pasadas).
- [x] Verificada carga diferida estricta (solo índice 0 procesado inicialmente; caché en llamadas repetidas).
- [x] Verificada regla de sincronización de álbum y cola independiente de la playlist original.

### Resultado
Fase 3 completada y validada correctamente.

### Próximo paso
Fase 4: Integrar proveedores reales de metadatos y carátulas (MusicBrainz, Deezer, iTunes/Apple Music, Discogs, Spotify), sistema de puntuación multi-factor y subida validada con Pillow.

---

## 2026-11-26 — Fase 4: Proveedores musicales, scoring multi-factor y carátulas

### Implementación
- Implementado motor de puntuación multi-factor (`title`, `artists`, `duration`, consenso entre fuentes y combinación por campo con trazabilidad de procedencia) en `backend/services/metadata/scoring.py`.
- Implementados adaptadores reales asíncronos para **Deezer**, **iTunes / Apple Music**, **MusicBrainz** (con rate-limit 1 req/s y Cover Art Archive) y adaptadores configurables vía `.env` para **Discogs** y **Spotify** en `backend/services/metadata/providers.py`.
- Implementado agregador concurrente con caché TTL (`aggregator.py`) conectado como hook a `TrackProcessor`.
- Implementado servicio de carátulas (`artwork_service.py`) con validación real mediante **Pillow**, redimensionado/re-codificación JPEG compatible ID3, protección SSRF en descargas remotas y aislamiento de archivos subidos por sesión (`backend/api/artwork.py`).

### Archivos creados
- `backend/services/metadata/__init__.py`, `scoring.py`, `providers.py`, `aggregator.py`
- `backend/services/artwork/__init__.py`, `artwork_service.py`
- `backend/api/artwork.py`
- `backend/tests/test_phase4_metadata_artwork.py`

### Archivos modificados
- `backend/main.py`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Validación
- [x] Pruebas unitarias (`pytest backend/tests/ -v`: 21/21 pasadas).
- [x] Validación de scoring multi-fuente, parsers de los 5 proveedores, subida de imagen y rechazo de archivos maliciosos.

### Resultado
Fase 4 completada y validada.

### Próximo paso
Fase 5: Implementar el catálogo versionado de etiquetas (idioma y estado de ánimo), lector de metadatos originales `TCON`/`TLAN` y motor de inferencia con persistencia separada del MP3.

---

## 2026-11-26 — Fase 5: Sistema inteligente de etiquetas (Idioma y Estado de Ánimo)

### Implementación
- Implementado catálogo versionado (`v1.0.0`) reutilizable con identificadores estables `lang.*` y `mood.*` y registro persistente de etiquetas personalizadas en `backend/services/classification/catalog.py`.
- Implementada lectura de metadatos originales (`TCON`, `TLAN`, `TXXX`) con Mutagen en `backend/services/audio/id3_service.py` (incluyendo también la función base de escritura estricta ID3v2.3 de 4 frames).
- Implementado motor de inferencia inteligente (`classifier.py`) basado en género original, idioma original, señales regionales y escritura, con umbral mínimo de confianza (`0.55`) y límite de sugerencias para evitar asignaciones excesivas o inventadas.
- Añadidos endpoints `/api/v1/tags/catalog` y `/api/v1/sessions/{sid}/tracks/{tid}/tags` con persistencia separada en `backend/data/track_tags.json`.

### Archivos creados
- `backend/services/classification/__init__.py`, `catalog.py`, `classifier.py`
- `backend/services/audio/id3_service.py`
- `backend/api/tags.py`
- `backend/tests/test_phase5_classification.py`

### Archivos modificados
- `backend/api/artwork.py`, `backend/main.py`
- `docs/IMPLEMENTATION_STATUS.md`, `docs/DEVELOPMENT_LOG.md`

### Validación
- [x] Linter (`ruff check backend`: 0 errores).
- [x] Pruebas unitarias (`pytest backend/tests/ -v`: 26/26 pasadas).
- [x] Verificada inferencia directa desde frames `TCON`/`TLAN` de MP3 real y comportamiento conservador sin datos.

### Resultado
Fase 5 completada y validada.

### Próximo paso
Fase 6: Construir el frontend SPA en React + TypeScript + Vite + Tailwind CSS v4 + Lucide siguiendo fielmente la referencia visual de Lovable y conectarlo con el backend.

---

## 2026-11-26 — Fases 6, 7 y 8: Frontend SPA, exportación estricta ID3v2.3, cola de playlists, SSE y ZIP

### Implementación
- **Fase 6 (Frontend SPA)**: Creada aplicación React + TypeScript + Vite + Tailwind CSS v4 + Lucide en `frontend/` replicando la paleta OKLCH oscura con acento lima (`--primary`), tokens de etiquetas (`--lang` cian y `--mood` ámbar), tipografía Geist/Geist Mono y diseño responsive de 3 columnas (`HeaderBar`, `TrackNavBar`, `PlayerColumn`, `MetadataEditorColumn`, `SourcesArtworkColumn`, `ActionFooter`, `DownloadProgressDrawer`, `EmptyState`).
- **Fase 7 (Exportación individual)**: Implementado generador de nombres `nombrecancion_primerartista.mp3` con deduplicación (`backend/utils/filename.py`) y verificado `write_strict_id3_v23` eliminando todos los frames prohibidos y escribiendo exclusivamente `TIT2`, `TPE1`, `TALB` y `APIC`.
- **Fase 8 (Playlists completas, SSE y ZIP)**: Implementado `DownloadManager` con concurrencia configurable (`PLAYLIST_DOWNLOAD_CONCURRENCY`), enriquecimiento automático de pistas `pending` durante exportación por lotes, tolerancia a errores por canción, streaming SSE (`/api/v1/jobs/{job_id}/events`), cancelación y generación de archivo ZIP (`/api/v1/jobs/{job_id}/zip`).

### Archivos creados
- `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html`, `src/index.css`, `src/vite-env.d.ts`, `src/main.tsx`, `src/App.tsx`
- `frontend/src/types/music.ts`, `frontend/src/services/api.ts`
- `frontend/src/components/{HeaderBar,TrackNavBar,PlayerColumn,MetadataEditorColumn,SourcesArtworkColumn,EmptyState,ActionFooter,DownloadProgressDrawer}.tsx`
- `backend/utils/filename.py`
- `backend/workers/__init__.py`, `backend/workers/download_manager.py`
- `backend/api/downloads.py`
- `backend/tests/test_phase7_8_export_and_playlist.py`

### Archivos modificados
- `backend/main.py`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Validación
- [x] Compilación Frontend (`tsc -b && vite build`: 0 errores).
- [x] Linter Backend (`ruff check backend`: 0 errores).
- [x] Pruebas Backend (`pytest backend/tests/ -v`: 29/29 pasadas, incluyendo inspección binaria Mutagen de MP3 dentro del ZIP).

### Resultado
Fases 6, 7 y 8 completadas y validadas.

### Próximo paso
Fase 9: Ejecutar pruebas de seguridad/aislamiento/SSE, completar documentación (`README.md`, `docs/SETUP.md`) y realizar verificación integral con servidores reales en ejecución.

---

## 2026-11-26 — Fase 9: Seguridad, SSE, validación en vivo y documentación final

### Implementación
- Añadidas pruebas de seguridad e integración (`backend/tests/test_phase9_security_and_sse.py`): aislamiento estricto entre sesiones, bloqueo de path traversal, rechazo honesto de descarga en URLs DRM sin crear archivos falsos, persistencia independiente de etiquetas y streaming real Server-Sent Events (`text/event-stream`).
- Verificada búsqueda real en vivo contra las APIs oficiales de **Deezer**, **MusicBrainz** e **iTunes / Apple Music**, y refinada la combinación multi-fuente en `backend/services/metadata/scoring.py` para priorizar el álbum de estudio real frente a títulos de single cuando dos fuentes de alta confianza coinciden.
- Redactada documentación completa para usuarios y desarrolladores (`README.md`, `docs/SETUP.md`) y actualizado el estado final en `docs/IMPLEMENTATION_STATUS.md`.

### Archivos creados
- `backend/tests/test_phase9_security_and_sse.py`
- `README.md`
- `docs/SETUP.md`

### Archivos modificados
- `backend/services/metadata/scoring.py`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Validación
- [x] Linter Python (`ruff check backend`: 0 errores).
- [x] TypeScript + Vite build (`npm --prefix frontend run lint` y `build`: 0 errores).
- [x] Suite completa de pruebas (`pytest backend/tests/ -v`: 32/32 pasadas).
- [x] Consulta real en vivo a Deezer, MusicBrainz e iTunes/Apple Music verificada con combinación multi-fuente y trazabilidad de procedencia.

### Resultado
Proyecto completo (Fases 1 a 9) implementado, probado y documentado.
