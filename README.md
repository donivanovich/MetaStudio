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
- **Búsqueda Inteligente de Metadatos y Carátulas**: Combina resultados de **Deezer**, **iTunes / Apple Music**, **MusicBrainz + Cover Art Archive** (sin claves requeridas) y adaptadores configurables de **Discogs** y **Spotify** mediante puntuación multi-factor y trazabilidad por campo.
- **Escritura Estricta ID3v2.3 (Mutagen)**: Elimina todos los frames previos y escribe exclusivamente `TIT2`, `TPE1`, `TALB` y `APIC` (imagen frontal).
- **Formato Obligatorio de Nombres**: `nombrecancion_primerartista.mp3` (p. ej. `callaita_bad_bunny.mp3`, `la_noche_de_anoche_bad_bunny.mp3`) con deduplicación segura.
- **Sistema Independiente de Etiquetas (v1.0.0)**: Utiliza `TCON`/`TLAN` originales y géneros de proveedores para sugerir idioma y estado de ánimo con nivel de confianza, guardándolos por separado (`backend/data/track_tags.json`) para reutilización futura sin escribirlos nunca en el MP3.
- **Descarga Individual y de Playlists Completas**: Cola independiente de la playlist original, concurrencia controlada, progreso en tiempo real (SSE), tolerancia a fallos individuales y empaquetado automático en **ZIP**.

---

## Inicio Rápido

```powershell
# 1. Configurar entorno (opcional para Discogs/Spotify)
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

## Documentación del Proyecto

- [Guía completa de instalación y configuración](docs/SETUP.md)
- [Arquitectura e inventario de módulos](docs/ARCHITECTURE.md)
- [Catálogo versionado de etiquetas inteligentes](docs/TAG_CATALOG.md)
- [Estado de implementación y trazabilidad](docs/IMPLEMENTATION_STATUS.md)
- [Registro incremental de desarrollo](docs/DEVELOPMENT_LOG.md)
