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

---

## 2026-11-26 — Fase 10: Dockerización completa y documentación operativa

### Implementación
- Creado `backend/Dockerfile` sobre `python:3.12-slim` con instalación nativa de `ffmpeg` y `ca-certificates`, instalación cacheada de dependencias Python, usuario no-root (`appuser`, UID 1000), healthcheck sobre `/api/v1/health` y ejecución de Uvicorn con `--proxy-headers --forwarded-allow-ips=*`.
- Creado `frontend/Dockerfile` multi-stage (`node:22-alpine` → `nginx:1.27-alpine`) con build determinista (`npm ci` + `npm run build`), `VITE_API_BASE_URL=""` por defecto para comunicación same-origin y healthcheck en `/healthz`.
- Creado `frontend/nginx.conf` con fallback SPA, caché inmutable para `/assets/`, límite de subida de `30m` para carátulas personalizadas y bloque dedicado para SSE (`/api/v1/jobs/<id>/events`) sin buffering ni compresión gzip y timeout de `3600s`.
- Creado `docker-compose.yml` con red dedicada (`metastudio-net`), volúmenes persistentes (`metastudio_data` y `metastudio_tmp`), `env_file` opcional (`required: false`), sobrescritura segura de rutas/host del contenedor y dependencia ordenada (`depends_on: condition: service_healthy`).
- Añadidos `.dockerignore` (raíz) y `frontend/.dockerignore` para reducir el contexto de build y excluir secretos y artefactos temporales.
- Redactada guía completa de despliegue en `docs/DOCKER.md` y actualizados `README.md`, `docs/SETUP.md`, `docs/ARCHITECTURE.md`, `.env.example` y `docs/IMPLEMENTATION_STATUS.md`.

### Archivos creados
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `docker-compose.yml`
- `.dockerignore`
- `frontend/.dockerignore`
- `docs/DOCKER.md`

### Archivos modificados
- `.env.example`
- `README.md`
- `docs/SETUP.md`
- `docs/ARCHITECTURE.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEVELOPMENT_LOG.md`

### Motivo del cambio
Permitir desplegar y ejecutar MetaStudio de forma reproducible en cualquier entorno mediante Docker y Docker Compose, sin instalación manual de Python, Node.js ni FFmpeg, manteniendo soporte íntegro para SSE, descargas ZIP y persistencia de etiquetas.

### Validación
- [x] Validación de esquema y resolución de variables con `docker compose config` (código de salida `0`, sin advertencias).
- [x] Revisión de contextos de build (`.dockerignore` y `frontend/.dockerignore`), cabeceras proxy/SSE en Nginx y aislamiento de permisos no-root.
- [x] Build y ejecución real en Docker Desktop (`docker compose up -d`), verificando asignación automática en rango (`8080-8099` → `8081` al estar `8080` ocupado, `8000-8019` → `8000`).
- [x] Verificación en vivo de `/healthz`, proxy inverso `/api/v1/health` (FFmpeg nativo 7.1.5 `system_path`, `yt-dlp`) y suite completa de pruebas dentro del contenedor (`docker compose exec -T backend pytest backend/tests/ -q`: 32/32 pasadas).

### Resultado
Dockerización con rangos de puertos automáticos y documentación operativa completadas, probadas en vivo y subidas al repositorio.

---

## 2026-11-26 — Fase 11: Normalización de títulos/feat., artistas colaboradores completos e identidad visual (logo y favicon)

### Implementación
- Creado módulo centralizado `backend/utils/metadata_normalizer.py` para:
  - Extraer cláusulas `feat.`, `ft.`, `featuring`, `with`, `con` (tanto entre paréntesis/corchetes como en línea y bloques mixtos tipo `(Remix feat. ...)`) y mover automáticamente todos los colaboradores al listado estructurado de `artists` con deduplicación insensible a acentos/mayúsculas.
  - Reformatear calificadores de versión entre paréntesis/corchetes o guion (p. ej. `LA VERDAD (remix) feat. No se quien` → título `LA VERDAD remix` + colaboradores en `artists`).
  - Corregir el separador de artistas (`\s+[x×]\s+`, `\s+y\s+`, `,`, `&`, `;`, `\s+with\s+`, `\s+con\s+`) evitando falsos cortes en nombres terminados en `x` (`Alex Rose`, `Dalex`) y protegiendo títulos normales (`Con Altura`, `Dancing With Myself`).
- Mejorada la captura completa de colaboradores en todos los proveedores y extracción:
  - **Deezer (`providers.py`)**: Enriquecimiento concurrente mediante `GET /track/{id}` para recuperar `contributors` completos (que `/search` omite).
  - **Apple Music / iTunes, MusicBrainz, Discogs y Spotify (`providers.py`)**: Normalización uniforme de títulos y división completa de múltiples artistas (`A, B & C` + `[feat. ...]`).
  - **yt-dlp (`ytdlp_service.py`)**: Extracción de todos los colaboradores en títulos `"Artista 1 x Artista 2 - Título"` incluso cuando `uploader`/`artist` contiene solo un artista principal, y rescate de colaboradores desde el título completo del vídeo cuando el campo `track` viene recortado.
  - **Scoring y Agregador (`scoring.py`, `aggregator.py`)**: Combinación multi-fuente que fusiona colaboradores confirmados entre fuentes de alta confianza y preserva colaboradores explícitos del título original.
- Diseñada e integrada identidad visual propia de **MetaStudio** (escudo oscuro con onda en forma de "M" en verde lima eléctrico y nodos de etiqueta cian/ámbar):
  - `frontend/public/favicon.svg`, `frontend/public/logo.svg`, `frontend/public/favicon-32x32.png`, `frontend/public/apple-touch-icon.png` y `frontend/public/favicon.ico`.
  - Componente reutilizable `frontend/src/components/BrandLogo.tsx` integrado en `HeaderBar` y `EmptyState`, y enlaces de favicon/theme-color en `frontend/index.html`.

### Archivos creados
- `backend/utils/metadata_normalizer.py`
- `backend/tests/test_metadata_normalizer.py`
- `frontend/public/favicon.svg`
- `frontend/public/logo.svg`
- `frontend/public/favicon-32x32.png`
- `frontend/public/apple-touch-icon.png`
- `frontend/public/favicon.ico`
- `frontend/src/components/BrandLogo.tsx`

### Archivos modificados
- `backend/services/downloader/ytdlp_service.py`
- `backend/services/metadata/providers.py`
- `backend/services/metadata/scoring.py`
- `backend/services/metadata/aggregator.py`
- `backend/api/sessions.py`
- `frontend/index.html`
- `frontend/src/components/HeaderBar.tsx`
- `frontend/src/components/EmptyState.tsx`
- `docs/DEVELOPMENT_LOG.md`

### Motivo del cambio
Garantizar que no se pierdan artistas colaboradores al analizar y enriquecer pistas desde YouTube/Deezer/iTunes/MusicBrainz, estandarizar el formato limpio de versiones y `feat.` en títulos y dotar a la aplicación web de un logotipo y favicon acordes a su identidad oscura minimalista.

### Validación
- [x] Linter Python (`docker compose exec -T backend ruff check backend`: 0 errores).
- [x] Suite completa de pruebas (`docker compose exec -T backend pytest backend/tests/ -q`: 42/42 pasadas, incluyendo 10 pruebas nuevas de normalización de títulos, `feat.`, `(remix)`, Deezer `/track/{id}` contributors y fusión multi-fuente).
- [x] Build de producción Frontend (`tsc -b && vite build` en Docker: 0 errores) y verificación HTTP 200 en vivo de `/favicon.svg`, `/logo.svg`, `/favicon.ico` y `/api/v1/health`.

### Resultado
Fase 11 implementada, verificada en contenedores vivos y lista en `main`.

---

## 2026-11-26 — Fase 12: Selector normalizado por campo, carátula YouTube JPEG predeterminada, título limpio y Spotify API

### Implementación
- Añadida `normalize_album_name` en `backend/utils/metadata_normalizer.py` y aplicada en todos los proveedores (`Deezer`, `Apple Music`, `MusicBrainz`, `Discogs`, `Spotify`), `yt-dlp`, `scoring.py` y `apply-candidate` (eliminando `- Single`, ruido de plataforma, cláusulas `feat.` y paréntesis de versión).
- Incluido candidato normalizado de origen (`YouTube` / `YouTube Music`) en `track.metadata_candidates` junto a los proveedores externos para poder alternar entre todas las fuentes normalizadas.
- Priorizada la carátula **YouTube / YouTube Music JPEG** como primera opción y carátula predeterminada al enriquecer pistas en `backend/services/metadata/aggregator.py` y `backend/services/track_processor.py` (respetando siempre carátulas subidas por el usuario).
- Añadido selector visual por campo (`FieldSourceSwitcher`) directamente debajo de *Nombre de la canción*, *Artistas* y *Álbum* en `frontend/src/components/MetadataEditorColumn.tsx` (además de botones por campo en `SourcesArtworkColumn.tsx`), permitiendo cambiar cada metadato entre las fuentes normalizadas igual que con las carátulas.
- Actualizado `<title>` de `frontend/index.html` a `MetaStudio` únicamente.
- Configuradas credenciales de Spotify Web API localmente en `.env` (excluido de Git y del contexto de build).

### Archivos modificados
- `backend/utils/metadata_normalizer.py`
- `backend/services/metadata/providers.py`
- `backend/services/metadata/scoring.py`
- `backend/services/metadata/aggregator.py`
- `backend/services/downloader/ytdlp_service.py`
- `backend/services/track_processor.py`
- `backend/api/sessions.py`
- `backend/tests/test_metadata_normalizer.py`
- `frontend/index.html`
- `frontend/src/App.tsx`
- `frontend/src/components/MetadataEditorColumn.tsx`
- `frontend/src/components/SourcesArtworkColumn.tsx`
- `docs/DEVELOPMENT_LOG.md`

---

## 2026-11-26 — Fase 13: Proveedores predeterminados (Álbum YT Music, Artistas Apple Music) y extracción pública Spotify oEmbed

### Implementación
- Priorizado **YouTube Music / YouTube** como proveedor predeterminado del nombre del **álbum** en `backend/services/metadata/aggregator.py` y `backend/services/track_processor.py` (y ordenado primero en el selector de álbum de `MetadataEditorColumn.tsx`).
- Priorizado **Apple Music** como proveedor predeterminado de **artistas** en `backend/services/metadata/scoring.py` y `aggregator.py` (y ordenado primero en el selector de artistas de `MetadataEditorColumn.tsx`), manteniendo el fallback multi-fuente cuando Apple Music no coincida.
- Añadida extracción oficial mediante **Spotify oEmbed** (`fetch_spotify_oembed` en `backend/services/metadata/providers.py` e integrado en `backend/api/sessions.py`) para obtener título y carátula oficial de Spotify sin requerir Premium en enlaces `open.spotify.com/...`, junto con estado transparente de la API de Spotify (`spotify_status` en `/api/v1/health` y aviso discreto en `SourcesArtworkColumn.tsx` cuando Spotify Web API devuelve `403 Active premium subscription required`).

### Archivos modificados
- `backend/services/metadata/providers.py`
- `backend/services/metadata/scoring.py`
- `backend/services/metadata/aggregator.py`
- `backend/services/track_processor.py`
- `backend/api/sessions.py`
- `backend/main.py`
- `backend/tests/test_metadata_normalizer.py`
- `frontend/src/types/music.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/MetadataEditorColumn.tsx`
- `frontend/src/components/SourcesArtworkColumn.tsx`
- `docs/DEVELOPMENT_LOG.md`

---

## 2026-11-26 — Fase 14: Eliminación completa de Spotify, selector desplegable integrado por campo y mejoras UI

### Implementación
- Eliminado completamente el proveedor, credenciales, tokens, avisos, tarjetas y referencias de Spotify de todo el proyecto (backend, frontend, Docker Compose, `.env`, `.env.example`, tests y documentación).
- Reemplazado el indicador estático del proveedor activo a la derecha de los encabezados (*Nombre de la canción*, *Artistas*, *Álbum*) por un selector desplegable personalizado (`FieldSourceSelect`) integrado con el diseño oscuro de MetaStudio, con ítems clicables (`SelectItem`) que muestran cada fuente y su vista previa normalizada.
- Eliminada la ayuda redundante *"Separados por coma y espacio · ej. Bad Bunny, Feid"* debajo del campo *Artistas*.
- Cambiado el botón principal de cabecera de *"Analizar"* / *"Analizando..."* a *"Extraer"* / *"Extrayendo..."*.

---

## 2026-11-26 — Fase 15: Scrollbar tematizado, indicador deslizante de 13 puntos y panel de descarga optimizado para playlists grandes

### Implementación
- Personalizado el scrollbar global en `frontend/src/index.css` con fondo del mismo color que la web (`--background`), barra deslizante (`thumb`) y flechas (`::-webkit-scrollbar-button:single-button`) en el verde lima de contraste (`--primary`), con fallback `scrollbar-color` para Firefox.
- Rediseñado el contador visual de puntos en `frontend/src/components/TrackNavBar.tsx` como ventana deslizante en una única línea de 13 círculos: desde la canción 1 hasta la 7 el punto activo avanza al centro, permanece centrado en toda la playlist y se desplaza hacia la derecha al llegar a las últimas 7 canciones.
- Eliminados los botones por archivo descargado en `frontend/src/components/DownloadProgressDrawer.tsx` (que generaban cientos de botones en playlists grandes de 300+ canciones), mostrando únicamente el botón de descarga del ZIP y un listado compacto con scroll únicamente para las canciones que hayan tenido error.

---

## 2026-11-26 — Fase 16: Botón «Limpiar cola» y metadatos de previsualización al compartir enlaces (Open Graph / Twitter Card)

### Implementación
- Añadido endpoint `DELETE /api/v1/sessions/{session_id}/queue` en `backend/api/sessions.py` para vaciar toda la cola de descarga sin modificar la playlist original cargada, con prueba automatizada en `backend/tests/test_phase3_playlists.py`.
- Añadido cliente `clearQueue` en `frontend/src/services/api.ts`, manejador `handleClearQueue` en `frontend/src/App.tsx` y botón **Limpiar cola** (`ListX`) en `frontend/src/components/ActionFooter.tsx`.
- Generada imagen social `frontend/public/og-image.png` (`1200×630`) acorde a la estética oscura + verde lima de MetaStudio y añadidas etiquetas `description`, Open Graph (`og:*`) y Twitter Card (`twitter:*`) en `frontend/index.html`.

---

## 2026-11-26 — Fase 17: Cabecera limpia, etiquetas de ánimo en verde lima, puertos Docker estables y guía Raspberry Pi

### Implementación
- Eliminadas las etiquetas de plataformas (`YT Music`, `YouTube`, `SoundCloud`) a la izquierda del botón **Extraer** en `frontend/src/components/HeaderBar.tsx`.
- Cambiado el token `--mood` en `frontend/src/index.css` a `var(--primary)` para que las etiquetas antes naranjas usen el verde lima de contraste de la aplicación.
- Corregida la deriva de puertos en Docker: `docker-compose.yml` usa puertos fijos (`${FRONTEND_PORT:-8080}:80` y `${BACKEND_HOST_PORT:-8000}:8000`) y añadidos los scripts `scripts/docker-up.ps1` (Windows) y `scripts/docker-up.sh` (Linux/macOS/Raspberry Pi, con `.gitattributes` LF) que mantienen el puerto actual de MetaStudio al reconstruir y solo saltan al siguiente puerto libre si está ocupado por otro servicio externo.
- Documentado el despliegue paso a paso en **Raspberry Pi (ARM64)** en `docs/DOCKER.md` y `README.md`.
