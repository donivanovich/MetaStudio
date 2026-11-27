# MetaStudio Music Downloader

Aplicación web profesional cliente-servidor para descargar canciones y playlists compatibles en **MP3** con **metadatos ID3v2.3 estrictos (4 campos)**, búsqueda inteligente multi-fuente, selección de carátulas en alta resolución y sistema independiente de etiquetas de idioma y estado de ánimo.

---

## Características Principales

- **Arquitectura Cliente-Servidor Real**: SPA web moderna (React + TypeScript + Vite + Tailwind CSS v4 + Lucide) conectada a un motor backend Python (**FastAPI + yt-dlp + FFmpeg + Mutagen + Pillow**) mediante REST API y **Server-Sent Events (SSE)**.
- **Interfaz de 3 Columnas (Estética Oscura Minimalista)**:
  - **Izquierda**: Reproductor de previsualizaciones autorizadas y vista previa en vivo de carátula y metadatos.
  - **Centro**: Editor estricto de los 4 elementos permitidos (*Carátula, Nombre de canción, Artistas, Álbum*) + gestor visual de etiquetas inteligentes (*Idioma* y *Estado de ánimo*).
  - **Derecha**: Comparador de fuentes musicales con puntuación de confianza y selector/subida de carátulas.
- **Carga Diferida (Lazy Loading) de Playlists**: Extrae playlists grandes en modo ligero (`extract_flat="in_playlist"`) y procesa inicialmente solo la primera canción; el resto se enriquece y cachea bajo demanda al navegar o al iniciar la descarga completa.
- **Búsqueda Inteligente de Metadatos y Carátulas**: Combina resultados de **Deezer**, **iTunes / Apple Music**, **MusicBrainz + Cover Art Archive** (sin claves requeridas) y adaptador configurable de **Discogs** mediante puntuación multi-factor y trazabilidad por campo.
- **Escritura Estricta ID3v2.3 (Mutagen)**: Elimina todos los frames previos y escribe exclusivamente `TIT2`, `TPE1`, `TALB` y `APIC` (imagen frontal).
- **Formato Obligatorio de Nombres**: `nombrecancion_primerartista.mp3` (p. ej. `callaita_bad_bunny.mp3`, `la_noche_de_anoche_bad_bunny.mp3`) con deduplicación segura.
- **Sistema Independiente de Etiquetas (v1.0.0)**: Utiliza `TCON`/`TLAN` originales y géneros de proveedores para sugerir idioma y estado de ánimo con nivel de confianza, guardándolos por separado (`backend/data/track_tags.json`) para reutilización futura sin escribirlos nunca en el MP3.
- **Descarga Individual y de Playlists Completas**: Cola independiente de la playlist original, concurrencia controlada, progreso en tiempo real (SSE), tolerancia a fallos individuales y empaquetado automático en **ZIP**.

---

## Inicio Rápido

### Opción 1: Docker Compose (Recomendado)

Requiere **Docker** y **Docker Compose v2** (incluye FFmpeg nativo, Nginx reverse proxy con soporte SSE y volúmenes persistentes):

```bash
# Linux / macOS / Raspberry Pi (elige automáticamente el primer puerto libre y lo mantiene estable entre cambios)
./scripts/docker-up.sh

# Windows PowerShell
.\scripts\docker-up.ps1

# O directamente con Docker Compose (puertos fijos definidos en .env o 8080/8000 por defecto)
docker compose up --build -d
```

Abre la URL que indique el script (por defecto `http://localhost:8080`, o el primer puerto libre si `8080` está ocupado por otro servicio).  
Consulta la guía completa (incluyendo despliegue en **Raspberry Pi**) en [docs/DOCKER.md](docs/DOCKER.md).

### Opción 2: Desarrollo Local (Python + Node.js)

```powershell
# 1. Configurar entorno (opcional para Discogs)
Copy-Item .env.example .env

# 2. Backend Python
python -m venv backend\.venv
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload

# 3. Frontend Web (en otra terminal)
npm --prefix frontend install
npm --prefix frontend run dev
```

Abre `http://localhost:5173` en tu navegador.

---

## CI/CD (GitHub Actions)

El repositorio incluye un pipeline automatizado de integración continua, entrega de imágenes Docker multi-arquitectura y despliegue opcional por SSH en servidor propio / Raspberry Pi, además de mantenimiento semanal con **Dependabot** (`.github/dependabot.yml`).

### Workflows disponibles

| Workflow | Archivo | Cuándo se ejecuta | Qué valida / hace |
| --- | --- | --- | --- |
| **CI** | `.github/workflows/ci.yml` | `push` a `main`, `pull_request` hacia `main` y manual (`workflow_dispatch`) | **Backend** (Python 3.12, FFmpeg nativo, `ruff check backend`, `pytest backend/tests/ -v`), **Frontend** (Node 22, `npm ci`, `npm run lint` [`tsc --noEmit`], `npm run build`, `npm audit --omit=dev --audit-level=high`), **Docker** (`docker compose config`, build de ambas imágenes con caché Buildx y smoke test en vivo contra `/healthz` y `/api/v1/health`), y **Scripts** (`shellcheck scripts/docker-up.sh`). |
| **CD — Publish Docker Images (GHCR)** | `.github/workflows/cd-ghcr.yml` | Al completarse con éxito `CI` en `push` a `main`, al subir tags SemVer (`v*.*.*`) y manual | Construye y publica imágenes multi-arquitectura (`linux/amd64`, `linux/arm64`) en **GitHub Container Registry** (`ghcr.io/<owner>/metastudio-backend` y `ghcr.io/<owner>/metastudio-frontend`) con tags trazables (`sha-<commit>`, `main`, versión SemVer y `latest`). |
| **CD — Deploy to Raspberry Pi (SSH)** | `.github/workflows/cd-raspberry-pi.yml` | Manual (`workflow_dispatch`) o automático tras `CD — Publish Docker Images (GHCR)` **solo si** la variable `RPI_AUTO_DEPLOY=true` | Conecta por SSH a la Raspberry Pi / VPS, actualiza al commit verificado, ejecuta `./scripts/docker-up.sh`, comprueba `/healthz` y `/api/v1/health`, y realiza **rollback automático** al commit anterior si algo falla. |

### Secretos y variables de GitHub

- **CI y publicación en GHCR**: No requieren secretos manuales (utilizan el `GITHUB_TOKEN` efímero con permisos mínimos `contents: read` y `packages: write` solo en el job de publicación).
- **Despliegue en Raspberry Pi / VPS (`environment: production`)**: Configura estos secretos en **Settings → Environments → `production`** (o en **Settings → Secrets and variables → Actions**):

| Tipo | Nombre | Obligatorio | Descripción |
| --- | --- | --- | --- |
| Secret | `RPI_HOST` | Sí (para SSH CD) | IP o dominio accesible por SSH de la Raspberry Pi / VPS |
| Secret | `RPI_USER` | Sí (para SSH CD) | Usuario SSH con acceso al grupo `docker` |
| Secret | `RPI_SSH_KEY` | Sí (para SSH CD) | Clave privada SSH dedicada al despliegue (sin passphrase) |
| Secret | `RPI_APP_DIR` | Sí (para SSH CD) | Ruta absoluta del clon en la Pi (p. ej. `/home/pi/MetaStudio`) |
| Secret | `RPI_PORT` | Opcional | Puerto SSH (por defecto `22`) |
| Secret | `RPI_SSH_KNOWN_HOSTS` | Recomendado | Salida de `ssh-keyscan -p <puerto> -H <host>` para verificación estricta de host |
| Variable | `RPI_AUTO_DEPLOY` | Opcional | Fijar a `true` para desplegar automáticamente tras cada publicación en GHCR (si no existe o es distinto de `true`, solo corre bajo disparo manual) |

### Cómo consultar ejecuciones y actuar ante fallos

1. Abre la pestaña **Actions** del repositorio en GitHub para ver el estado por workflow y job (`backend`, `frontend`, `docker`, `scripts`).
2. Si falla un job de **CI**:
   - **Backend (`ruff` o `pytest`)**: reproduce localmente con `ruff check backend` y `pytest backend/tests/ -v`.
   - **Frontend (`lint`, `build` o `npm audit`)**: reproduce con `npm --prefix frontend ci`, `npm --prefix frontend run lint` y `npm --prefix frontend run build`.
   - **Docker (build o smoke test)**: revisa los logs volcados automáticamente por el step y prueba `docker compose config` y `docker compose up --build -d`.
   - **Scripts (`shellcheck`)**: revisa las advertencias de `scripts/docker-up.sh`.
3. Si falla **CD — Deploy to Raspberry Pi (SSH)**:
   - El workflow intenta automáticamente volver al commit previo (`PREV_SHA`) y verificar `/healthz` + `/api/v1/health`.
   - Revisa el resumen del job en **Actions** y, si hace falta, conéctate por SSH a la Pi para consultar `docker compose ps` y `docker compose logs --tail=100`.

---

## Documentación del Proyecto

- [Guía de despliegue con Docker](docs/DOCKER.md)
- [Guía completa de instalación y configuración local](docs/SETUP.md)
- [Arquitectura e inventario de módulos](docs/ARCHITECTURE.md)
- [Catálogo versionado de etiquetas inteligentes](docs/TAG_CATALOG.md)
- [Estado de implementación y trazabilidad](docs/IMPLEMENTATION_STATUS.md)
- [Registro incremental de desarrollo](docs/DEVELOPMENT_LOG.md)
