"""Async single-track and controlled-concurrency playlist download manager with SSE & ZIP."""

import asyncio
import logging
import shutil
import uuid
import zipfile
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from backend.config.settings import get_settings
from backend.models.domain import SessionState, TrackState, TrackStatus
from backend.schemas.api import DownloadJobResponse
from backend.services.artwork.artwork_service import fetch_selected_artwork_bytes
from backend.services.audio.id3_service import read_original_id3_metadata, write_strict_id3_v23
from backend.services.classification.classifier import classify_track
from backend.services.downloader.ytdlp_service import DownloadServiceError, ytdlp_service
from backend.services.storage.store import session_store
from backend.services.track_processor import track_processor
from backend.utils.filename import build_mp3_filename, deduplicate_filename

logger = logging.getLogger(__name__)


@dataclass
class DownloadJob:
    """Runtime state of a single-track or full-playlist export job."""

    job_id: str
    session_id: str
    job_type: str  # "single" | "playlist"
    track_ids: list[str]
    status: str = "queued"  # queued | running | completed | failed | cancelled
    completed_tracks: int = 0
    failed_tracks: int = 0
    current_track_id: str | None = None
    current_track_title: str | None = None
    current_track_progress: float = 0.0
    zip_path: Path | None = None
    files: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    cancelled: bool = False
    subscribers: list[asyncio.Queue[DownloadJobResponse]] = field(default_factory=list)

    def to_response(self) -> DownloadJobResponse:
        pending = max(0, len(self.track_ids) - self.completed_tracks - self.failed_tracks)
        zip_ready = bool(self.zip_path and self.zip_path.is_file())
        return DownloadJobResponse(
            job_id=self.job_id,
            session_id=self.session_id,
            job_type=self.job_type,
            status=self.status,
            total_tracks=len(self.track_ids),
            completed_tracks=self.completed_tracks,
            failed_tracks=self.failed_tracks,
            pending_tracks=pending,
            current_track_id=self.current_track_id,
            current_track_title=self.current_track_title,
            current_track_progress=round(self.current_track_progress, 1),
            zip_ready=zip_ready,
            zip_download_url=f"/api/v1/jobs/{self.job_id}/zip" if zip_ready else None,
            files=list(self.files),
            errors=list(self.errors),
        )


class DownloadManager:
    """Coordinates single MP3 exports, controlled-concurrency playlist queues, SSE, and ZIP archives."""

    def __init__(self) -> None:
        self._jobs: dict[str, DownloadJob] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def get_job(self, job_id: str) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def _notify(self, job: DownloadJob) -> None:
        snapshot = job.to_response()
        for queue in list(job.subscribers):
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull:
                pass

    async def subscribe(self, job_id: str) -> AsyncIterator[DownloadJobResponse]:
        job = self._jobs.get(job_id)
        if not job:
            return
        queue: asyncio.Queue[DownloadJobResponse] = asyncio.Queue(maxsize=64)
        job.subscribers.append(queue)
        try:
            yield job.to_response()
            if job.status in {"completed", "failed", "cancelled"}:
                return
            while True:
                try:
                    snapshot = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield snapshot
                    if snapshot.status in {"completed", "failed", "cancelled"}:
                        break
                except TimeoutError:
                    yield job.to_response()
                    if job.status in {"completed", "failed", "cancelled"}:
                        break
        finally:
            if queue in job.subscribers:
                job.subscribers.remove(queue)

    def start_single_download(self, session: SessionState, track: TrackState) -> DownloadJob:
        job_id = f"job-{uuid.uuid4().hex[:10]}"
        job = DownloadJob(
            job_id=job_id,
            session_id=session.session_id,
            job_type="single",
            track_ids=[track.id],
        )
        self._jobs[job_id] = job
        self._tasks[job_id] = asyncio.create_task(self._run_job(job, session))
        return job

    def start_playlist_download(self, session: SessionState) -> DownloadJob:
        track_ids = [tid for tid in session.queue_track_ids if session.get_track(tid) is not None]
        if not track_ids:
            raise ValueError("La cola de descarga está vacía.")

        job_id = f"job-{uuid.uuid4().hex[:10]}"
        job = DownloadJob(
            job_id=job_id,
            session_id=session.session_id,
            job_type="playlist",
            track_ids=track_ids,
        )
        self._jobs[job_id] = job
        self._tasks[job_id] = asyncio.create_task(self._run_job(job, session))
        return job

    def cancel_job(self, job_id: str) -> DownloadJob | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        if job.status in {"queued", "running"}:
            job.cancelled = True
            job.status = "cancelled"
            self._notify(job)
        return job

    async def _run_job(self, job: DownloadJob, session: SessionState) -> None:
        job.status = "running"
        self._notify(job)

        settings = get_settings()
        concurrency = 1 if job.job_type == "single" else settings.playlist_download_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        used_filenames: set[str] = set()
        name_lock = asyncio.Lock()

        exports_dir = session_store.get_session_dir(session.session_id) / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()

        async def _worker(track_id: str) -> None:
            async with semaphore:
                if job.cancelled:
                    return
                track = session.get_track(track_id)
                if not track:
                    return

                job.current_track_id = track.id
                job.current_track_title = track.title
                job.current_track_progress = 2.0
                track.status = TrackStatus.DOWNLOADING
                track.download_progress = 2.0
                track.error_message = None
                self._notify(job)

                try:
                    await self._process_and_export_track(
                        job=job,
                        session=session,
                        track=track,
                        exports_dir=exports_dir,
                        used_filenames=used_filenames,
                        name_lock=name_lock,
                        loop=loop,
                    )
                    job.completed_tracks += 1
                    job.files.append(
                        {
                            "track_id": track.id,
                            "file_name": track.downloaded_file_name or "track.mp3",
                            "download_url": f"/api/v1/sessions/{session.session_id}/tracks/{track.id}/file",
                        }
                    )
                except Exception as exc:
                    logger.warning("Track %s export failed: %s", track.id, exc)
                    track.status = TrackStatus.ERROR
                    track.error_message = str(exc)
                    track.download_progress = 0.0
                    job.failed_tracks += 1
                    job.errors.append(
                        {
                            "track_id": track.id,
                            "title": track.title,
                            "error": str(exc),
                        }
                    )
                finally:
                    session_store.save_session(session)
                    self._notify(job)

        await asyncio.gather(*(_worker(tid) for tid in job.track_ids))

        if job.cancelled:
            job.status = "cancelled"
            self._notify(job)
            return

        # Package ZIP for playlist jobs when at least one MP3 succeeded
        if job.job_type == "playlist" and job.completed_tracks > 0:
            zip_file = exports_dir / f"metastudio_{job.job_id}.zip"
            with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_info in job.files:
                    track = session.get_track(file_info["track_id"])
                    if track and track.downloaded_file_path:
                        mp3_path = Path(track.downloaded_file_path)
                        if mp3_path.is_file():
                            zf.write(mp3_path, arcname=file_info["file_name"])
            job.zip_path = zip_file

        if job.completed_tracks == 0 and job.failed_tracks > 0:
            job.status = "failed"
        else:
            job.status = "completed"
        job.current_track_progress = 100.0 if job.status == "completed" else 0.0
        self._notify(job)

    async def _process_and_export_track(
        self,
        *,
        job: DownloadJob,
        session: SessionState,
        track: TrackState,
        exports_dir: Path,
        used_filenames: set[str],
        name_lock: asyncio.Lock,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Execute full export pipeline for one track using its latest saved edits."""
        if not track.audio_downloadable:
            raise DownloadServiceError(
                "Esta plataforma está protegida con DRM y no permite descarga directa de audio."
            )

        # Ensure lazy-loaded pending tracks are enriched before downloading
        if track.status == TrackStatus.PENDING or (
            not track.metadata_candidates and not track.artwork_candidates
        ):
            await track_processor.process_track(session, track)
            track.status = TrackStatus.DOWNLOADING
            job.current_track_title = track.title
            self._notify(job)

        def _on_progress(pct: float, _stage: str) -> None:
            track.download_progress = pct
            job.current_track_id = track.id
            job.current_track_title = track.title
            job.current_track_progress = pct
            loop.call_soon_threadsafe(self._notify, job)

        work_dir = session_store.get_session_dir(session.session_id) / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        temp_stem = f"{track.id}_{uuid.uuid4().hex[:6]}"

        raw_mp3 = await asyncio.to_thread(
            ytdlp_service.download_audio_mp3,
            track.source_url,
            work_dir,
            temp_stem,
            _on_progress,
        )

        try:
            # Rule 11.3: Read original MP3 TCON/TLAN (if any) for smart classification BEFORE stripping
            orig_id3 = read_original_id3_metadata(raw_mp3)
            if orig_id3.genres or orig_id3.languages:
                track.original_genres = list(dict.fromkeys([*orig_id3.genres, *track.original_genres]))
                if orig_id3.languages and not track.original_language:
                    track.original_language = orig_id3.languages[0]
                track.suggested_tags = classify_track(
                    title=track.title,
                    artists=track.artists,
                    original_genres=track.original_genres,
                    original_language=track.original_language,
                    mp3_path=raw_mp3,
                )

            # Fetch selected artwork (always using the latest user selection)
            artwork_payload = await fetch_selected_artwork_bytes(session.session_id, track)
            art_bytes, art_mime = artwork_payload if artwork_payload else (None, "image/jpeg")

            # Rule 15: Strip ALL extraneous frames and write EXCLUSIVELY TIT2, TPE1, TALB, APIC (ID3v2.3)
            final_album = track.album.strip() if track.album and track.album.strip() else track.title
            write_strict_id3_v23(
                raw_mp3,
                title=track.title,
                artists=track.artists,
                album=final_album,
                artwork_bytes=art_bytes,
                artwork_mime=art_mime,
            )

            # Rule 16: Strict filename `nombrecancion_primerartista.mp3` with collision avoidance
            base_name = build_mp3_filename(track.title, track.artists)
            async with name_lock:
                final_name = deduplicate_filename(base_name, used_filenames)

            final_path = exports_dir / final_name
            shutil.move(str(raw_mp3), str(final_path))

            track.downloaded_file_name = final_name
            track.downloaded_file_path = str(final_path)
            track.download_progress = 100.0
            track.status = TrackStatus.DOWNLOADED
        except Exception:
            raw_mp3.unlink(missing_ok=True)
            raise


download_manager = DownloadManager()
