"""Endpoints for single MP3 export, full playlist downloads, SSE live progress, and ZIP delivery."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from backend.schemas.api import DownloadJobResponse
from backend.services.storage.store import session_store
from backend.workers.download_manager import download_manager

router = APIRouter(prefix="/api/v1", tags=["downloads"])


@router.post(
    "/sessions/{session_id}/tracks/{track_id}/download",
    response_model=DownloadJobResponse,
)
async def download_single_track(session_id: str, track_id: str):
    """Queue an asynchronous download & strict ID3 export for a single track."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Canción no encontrada.")
    if not track.audio_downloadable:
        raise HTTPException(
            status_code=400,
            detail="Esta plataforma está protegida con DRM y no proporciona descarga directa de audio.",
        )

    job = download_manager.start_single_download(session, track)
    return job.to_response()


@router.post(
    "/sessions/{session_id}/download-playlist",
    response_model=DownloadJobResponse,
)
async def download_full_playlist(session_id: str):
    """Start controlled-concurrency batch download for all tracks in the session's queue."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    try:
        job = download_manager.start_playlist_download(session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.to_response()


@router.get("/jobs/{job_id}", response_model=DownloadJobResponse)
async def get_download_job(job_id: str):
    job = download_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de descarga no encontrado.")
    return job.to_response()


@router.post("/jobs/{job_id}/cancel", response_model=DownloadJobResponse)
async def cancel_download_job(job_id: str):
    job = download_manager.cancel_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de descarga no encontrado.")
    return job.to_response()


@router.get("/jobs/{job_id}/events")
async def stream_download_job_events(job_id: str):
    """Stream real-time download & conversion progress via Server-Sent Events (SSE)."""
    job = download_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de descarga no encontrado.")

    async def _event_generator():
        async for snapshot in download_manager.subscribe(job_id):
            yield f"data: {snapshot.model_dump_json()}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/tracks/{track_id}/file")
async def serve_exported_mp3(session_id: str, track_id: str):
    """Deliver a finished, session-isolated MP3 file to the browser."""
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    track = session.get_track(track_id)
    if not track or not track.downloaded_file_path or not track.downloaded_file_name:
        raise HTTPException(status_code=404, detail="Archivo MP3 aún no generado.")

    session_dir = session_store.get_session_dir(session_id).resolve()
    mp3_path = Path(track.downloaded_file_path).resolve()
    if session_dir not in mp3_path.parents or not mp3_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo MP3 no encontrado.")

    return FileResponse(
        mp3_path,
        media_type="audio/mpeg",
        filename=track.downloaded_file_name,
    )


@router.get("/jobs/{job_id}/zip")
async def serve_playlist_zip(job_id: str):
    """Deliver the finished playlist ZIP archive to the browser."""
    job = download_manager.get_job(job_id)
    if not job or not job.zip_path or not job.zip_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo ZIP no disponible.")

    session_dir = session_store.get_session_dir(job.session_id).resolve()
    zip_path = job.zip_path.resolve()
    if session_dir not in zip_path.parents:
        raise HTTPException(status_code=403, detail="Acceso denegado.")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"metastudio_playlist_{job.job_id}.zip",
    )
