# MetaStudio Music Downloader

Aplicación web profesional cliente-servidor para descargar canciones y playlists compatibles en **MP3** con **metadatos ID3v2.3 estrictos (4 campos)**, búsqueda inteligente multi-fuente, selección de carátulas en alta resolución y sistema independiente de etiquetas de idioma y estado de ánimo.

- **Producción**: [`https://metastudio.donivanovich.dev`](https://metastudio.donivanovich.dev) (Raspberry Pi 5 · 16 GB · Raspberry Pi OS Lite 64-bit · Docker Compose + Cloudflare Tunnel → `localhost:3200`, backend estrictamente interno).

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

### Opción 1: Producción en Raspberry Pi 5 / Servidor Linux (Docker Compose + GHCR)

No requiere Python, Node.js ni FFmpeg instalados en el host; utiliza imágenes multi-arquitectura (`linux/arm64`, `linux/amd64`) precompiladas en GHCR, mantiene el **backend estrictamente interno** (sin puerto público) y expone Nginx solo en `127.0.0.1:3200` para Cloudflare Tunnel (`metastudio.donivanovich.dev` → `localhost:3200`):

```bash
cd /opt/docker/apps/MetaStudio
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

# Verificar salud (Nginx + proxy interno hacia FastAPI y FFmpeg)
curl -fsS http://127.0.0.1:3200/healthz
curl -fsS http://127.0.0.1:3200/api/v1/health
```

Consulta la guía operativa completa (Cloudflare Tunnel, healthchecks, logs, diagnóstico, actualizaciones sin pérdida de datos y copias de seguridad de `metastudio_data`) en [docs/DOCKER.md](docs/DOCKER.md).

### Opción 2: Desarrollo Local con Docker (`docker-compose.yml`)

Compila ambos servicios desde el código local (frontend en `8080`, backend/Swagger en `8000`):

```bash
# Linux / macOS (selecciona el primer puerto libre y lo mantiene estable entre rebuilds)
./scripts/docker-up.sh

# Windows PowerShell
.\scripts\docker-up.ps1

# O directamente con Docker Compose
docker compose up --build -d
```

### Opción 3: Desarrollo Local sin Docker (Python + Node.js)

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
| **CI** | `.github/workflows/ci.yml` | `push` a `main`, `pull_request` hacia `main` y manual (`workflow_dispatch`) | **Backend** (Python 3.12, FFmpeg nativo, `ruff check backend`, `pytest backend/tests/ -v`), **Frontend** (Node 22, `npm ci`, `npm run lint`, `npm run build`) y **Docker** (validación de `docker-compose.yml` y `docker-compose.prod.yml`, build con caché Buildx y smoke test contra `/healthz` y `/api/v1/health`). |
| **Security Audit** | `.github/workflows/security-audit.yml` | `push` a `main`, `pull_request` hacia `main`, semanalmente (lunes 06:00 UTC) y manual | Auditoría independiente de seguridad: `npm audit --package-lock-only --omit=dev --audit-level=high`, `pip-audit` sobre Python 3.12, `shellcheck scripts/docker-up.sh` y verificación de que no existan `.env` ni claves privadas rastreadas en Git. |
| **CD — Publish Docker Images (GHCR)** | `.github/workflows/cd-ghcr.yml` | Al completarse con éxito `CI` en `push` a `main`, al subir tags SemVer (`v*.*.*`) y manual | Construye y publica imágenes multi-arquitectura (`linux/amd64`, `linux/arm64`) en **GitHub Container Registry** (`ghcr.io/<owner>/metastudio-backend` y `ghcr.io/<owner>/metastudio-frontend`) con tags trazables (`sha-<commit>`, `main`, versión SemVer y `latest`). |
| **CD — Deploy to Raspberry Pi 5 (SSH)** | `.github/workflows/cd-raspberry-pi.yml` | Manual (`workflow_dispatch`) o automático tras `CD — Publish Docker Images (GHCR)` en `main` **solo si** `vars.RPI_AUTO_DEPLOY == 'true'` | Conecta por SSH a la Raspberry Pi 5, sincroniza `docker-compose.prod.yml`, descarga las imágenes ARM64 nuevas (`docker compose pull`) sin detener el servicio actual, actualiza con `docker compose up -d`, verifica estado `healthy` + `/healthz` + `/api/v1/health` + digest de imagen en ejecución y ejecuta **rollback automático** a las imágenes previas si falla. |

### Secretos y variables de GitHub

- **CI, Security Audit y publicación en GHCR**: No requieren secretos manuales (utilizan el `GITHUB_TOKEN` efímero con privilegios mínimos).
- **Despliegue en Raspberry Pi 5 (`environment: production`)**: Configura estos secretos en **Settings → Environments → `production`**:

| Tipo | Nombre | Obligatorio | Descripción |
| --- | --- | --- | --- |
| Secret | `RPI_HOST` | Sí (para SSH CD) | IP o dominio accesible por SSH de la Raspberry Pi 5 |
| Secret | `RPI_USER` | Sí (para SSH CD) | Usuario SSH con acceso al grupo `docker` |
| Secret | `RPI_SSH_KEY` | Sí (para SSH CD) | Clave privada SSH dedicada al despliegue (sin passphrase) |
| Secret | `RPI_APP_DIR` | Sí (para SSH CD) | Directorio absoluto de despliegue en la Pi (`/opt/docker/apps/MetaStudio`) |
| Secret | `RPI_PORT` | Opcional | Puerto SSH (por defecto `22`) |
| Secret | `RPI_SSH_KNOWN_HOSTS` | Recomendado | Salida de `ssh-keyscan -p <puerto> -H <host>` para verificación estricta de host |
| Secret | `GHCR_USERNAME` / `GHCR_READ_TOKEN` | Solo si GHCR es privado | Usuario y PAT con permiso mínimo `read:packages` para `docker login ghcr.io` en la Pi |
| Variable | `RPI_AUTO_DEPLOY` | Opcional | Fijar a `true` para desplegar automáticamente tras cada publicación exitosa en GHCR desde `main` |

### Cómo consultar ejecuciones y actuar ante fallos

1. Abre la pestaña **Actions** del repositorio en GitHub para ver cada workflow independiente (`CI`, `Security Audit`, `CD — Publish Docker Images (GHCR)` y `CD — Deploy to Raspberry Pi 5 (SSH)`).
2. Si falla **CI** o **Security Audit**:
   - **Backend (`ruff` o `pytest`)**: reproduce con `ruff check backend` y `pytest backend/tests/ -v`.
   - **Frontend (`lint` o `build`)**: reproduce con `npm --prefix frontend ci`, `npm --prefix frontend run lint` y `npm --prefix frontend run build`.
   - **Docker**: valida `docker compose config`, `docker compose -f docker-compose.prod.yml config` y revisa los logs volcados por el smoke test.
   - **Security Audit**: revisa las vulnerabilidades reportadas por `npm audit` / `pip-audit` o avisos de `shellcheck`.
3. Si falla **CD — Deploy to Raspberry Pi 5 (SSH)**:
   - Si falló durante `docker compose pull`, los contenedores en producción **no fueron interrumpidos**.
   - Si falló al arrancar o en la verificación de salud, el workflow restaura automáticamente `docker-compose.prod.yml.bak` y las imágenes previas (`PREV_BACKEND_ID` / `PREV_FRONTEND_ID`) y verifica su recuperación.
   - Revisa los logs volcados en **Actions** o conéctate por SSH a la Pi (`docker compose -f docker-compose.prod.yml ps` y `logs --tail=100`).

---

## Documentación del Proyecto

- [Guía de despliegue con Docker](docs/DOCKER.md)
- [Guía completa de instalación y configuración local](docs/SETUP.md)
- [Arquitectura e inventario de módulos](docs/ARCHITECTURE.md)
- [Catálogo versionado de etiquetas inteligentes](docs/TAG_CATALOG.md)
- [Estado de implementación y trazabilidad](docs/IMPLEMENTATION_STATUS.md)
- [Registro incremental de desarrollo](docs/DEVELOPMENT_LOG.md)
