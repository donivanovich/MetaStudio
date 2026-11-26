# Guía de Instalación, Configuración y Solución de Problemas

## 1. Requisitos Previos

- **Python 3.11 o superior** (verificado con Python 3.14).
  - Windows: [python.org/downloads](https://www.python.org/downloads/) (marcar *"Add Python to PATH"*).
  - macOS: `brew install python`
  - Linux (Ubuntu/Debian): `sudo apt install python3 python3-venv python3-pip`
- **Node.js 20 LTS o superior** y **npm** (verificado con Node 24 y npm 11).
- **FFmpeg**:
  - **Opción A (automática incluida):** Al instalar `backend/requirements.txt`, `imageio-ffmpeg` incluye un binario oficial estático de FFmpeg que el backend detecta automáticamente sin configuración adicional.
  - **Opción B (instalación global recomendada en producción):**
    - Windows: `winget install Gyan.FFmpeg` o `choco install ffmpeg`
    - macOS: `brew install ffmpeg`
    - Linux: `sudo apt install ffmpeg`
  - **Opción C (ruta manual):** Define `FFMPEG_PATH=C:\ruta\a\ffmpeg.exe` en `.env`.

---

## 2. Configuración de Variables de Entorno

Copia la plantilla sin credenciales:

```powershell
Copy-Item .env.example .env
```

Variables principales en `.env`:

| Variable | Descripción | Obligatoria |
| --- | --- | --- |
| `BACKEND_HOST` / `BACKEND_PORT` | Host y puerto del servidor FastAPI (`127.0.0.1:8000`) | No |
| `CORS_ORIGINS` | Orígenes permitidos para el frontend (`http://localhost:5173`) | No |
| `FFMPEG_PATH` | Ruta explícita al binario `ffmpeg` (vacío = autodetección) | No |
| `AUDIO_MP3_BITRATE` | Bitrate MP3 en kbps (`192`, `256`, `320`) | No |
| `PLAYLIST_DOWNLOAD_CONCURRENCY` | Concurrencia controlada para playlists (`1`–`5`, por defecto `2`) | No |
| `MUSICBRAINZ_USER_AGENT` | User-Agent requerido por la API de MusicBrainz | No |
| `DISCOGS_TOKEN` | Personal Access Token de [Discogs Developers](https://www.discogs.com/settings/developers) | Opcional |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Credenciales Client Credentials de [Spotify Dashboard](https://developer.spotify.com/dashboard) | Opcional |
| `VITE_API_BASE_URL` | URL base del backend cuando frontend y backend se despliegan por separado | No (en dev Vite usa proxy; en Docker Nginx usa proxy) |
| `FRONTEND_PORT` | Puerto o rango público expuesto por Nginx en Docker Compose (`8080-8099`, salta puertos ocupados) | No (solo Docker) |
| `BACKEND_HOST_PORT` | Puerto o rango público expuesto por FastAPI en Docker Compose (`8000-8019`, salta puertos ocupados) | No (solo Docker) |

> **Nota:** **MusicBrainz**, **Deezer** e **iTunes / Apple Music** funcionan directamente sin claves API. Discogs y Spotify se activan automáticamente al introducir sus credenciales en `.env` (nunca se exponen al frontend).

---

## 2.5. Ejecución Rápida con Docker Compose (Alternativa Recomendada)

Si prefieres no instalar Python, Node.js ni FFmpeg localmente, puedes levantar toda la aplicación con un único comando:

```bash
docker compose up --build -d
```

- Interfaz web (Nginx + SPA + proxy `/api`): `http://localhost:8080`
- Backend healthcheck: `http://localhost:8000/api/v1/health`

Para volúmenes, personalización de puertos, actualización de `yt-dlp` y solución de problemas en contenedores, consulta [docs/DOCKER.md](DOCKER.md).

---

## 3. Instalación y Ejecución del Backend (Python / FastAPI)

```powershell
# 1. Crear entorno virtual
python -m venv backend\.venv

# 2. Instalar dependencias Python
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt

# 3. Iniciar servidor backend (puerto 8000)
backend\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Comprueba el estado de salud y FFmpeg en: `http://127.0.0.1:8000/api/v1/health`

---

## 4. Instalación y Ejecución del Frontend (React / Vite)

En una segunda terminal:

```powershell
# 1. Instalar dependencias Node
npm --prefix frontend install

# 2. Iniciar interfaz web (puerto 5173)
npm --prefix frontend run dev
```

Abre `http://localhost:5173` en tu navegador. Toda la interacción se realiza desde la aplicación web.

Para compilar una versión de producción:

```powershell
npm --prefix frontend run build
```

---

## 5. Actualizar `yt-dlp`

YouTube y otras plataformas cambian con frecuencia. Para mantener actualizada la extracción:

```powershell
backend\.venv\Scripts\pip.exe install -U yt-dlp
```

---

## 6. Ejecutar Pruebas y Linters

```powershell
# Linter Python
backend\.venv\Scripts\ruff.exe check backend

# Pruebas unitarias e integración Backend
backend\.venv\Scripts\pytest.exe backend\tests\ -v

# Verificación de tipos y build Frontend
npm --prefix frontend run lint
npm --prefix frontend run build
```

---

## 7. Solución de Errores Frecuentes

- **`FFmpeg no encontrado`**: Comprueba `GET /api/v1/health`. Instala FFmpeg globalmente o reinstala `imageio-ffmpeg` dentro de `backend\.venv`.
- **Error al extraer URL de YouTube**: Actualiza `yt-dlp` (`pip install -U yt-dlp`). Comprueba que el vídeo/playlist sea público y accesible sin DRM.
- **Enlace de Spotify / Apple Music / Deezer no descarga audio**: Por diseño legal y técnico, las plataformas con DRM no permiten descarga directa de audio; MetaStudio las utiliza como proveedores de metadatos, carátulas y previsualizaciones autorizadas.
- **CORS bloqueado al desplegar por separado**: Añade el dominio del frontend a `CORS_ORIGINS` en `.env` y configura `VITE_API_BASE_URL` en el build del frontend.
