import { AlertCircle, CheckCircle2, FolderArchive, Loader2, X } from "lucide-react";
import { resolveApiUrl } from "../services/api";
import type { DownloadJobResponse } from "../types/music";

interface DownloadProgressDrawerProps {
  job: DownloadJobResponse | null;
  onCancel: () => void;
  onDismiss: () => void;
}

export function DownloadProgressDrawer({
  job,
  onCancel,
  onDismiss,
}: DownloadProgressDrawerProps) {
  if (!job) return null;

  const isActive = job.status === "queued" || job.status === "running";
  const overallPct =
    job.total_tracks > 0
      ? Math.round(
          ((job.completed_tracks + job.failed_tracks + (isActive ? job.current_track_progress / 100 : 0)) /
            job.total_tracks) *
            100,
        )
      : 0;

  return (
    <div className="rounded-2xl border border-border bg-card/85 p-4 backdrop-blur">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {isActive ? (
            <Loader2 className="size-4 animate-spin text-primary" />
          ) : job.status === "completed" ? (
            <CheckCircle2 className="size-4 text-primary" />
          ) : (
            <AlertCircle className="size-4 text-destructive" />
          )}

          <div>
            <p className="text-sm font-medium text-foreground">
              {job.job_type === "playlist" ? "Descarga de playlist" : "Descarga individual"}
              {" · "}
              <span className="font-mono text-xs text-muted-foreground">
                {job.completed_tracks}/{job.total_tracks} completadas
                {job.pending_tracks > 0 ? ` · ${job.pending_tracks} pendientes` : ""}
                {job.failed_tracks > 0 ? ` · ${job.failed_tracks} con error` : ""}
              </span>
            </p>
            {isActive && job.current_track_title && (
              <p className="text-xs text-muted-foreground">
                Procesando: <span className="text-foreground">{job.current_track_title}</span> (
                {Math.round(job.current_track_progress)}%)
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {job.zip_ready && job.zip_download_url && (
            <a
              href={resolveApiUrl(job.zip_download_url)}
              download
              className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground transition-all hover:brightness-105"
            >
              <FolderArchive className="size-3.5" />
              <span>Descargar ZIP</span>
            </a>
          )}

          {isActive ? (
            <button
              type="button"
              onClick={onCancel}
              className="cursor-pointer rounded-xl border border-border bg-secondary px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-destructive"
            >
              Cancelar
            </button>
          ) : (
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Cerrar panel de descarga"
              className="cursor-pointer rounded-lg p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${Math.min(100, Math.max(0, overallPct))}%` }}
        />
      </div>

      {/* Errors only (never flood UI with per-file buttons on large playlists) */}
      {job.errors.length > 0 && (
        <div className="mt-3 max-h-40 space-y-1.5 overflow-y-auto pr-1">
          {job.errors.map((err) => (
            <div
              key={err.track_id}
              className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-2.5 py-1.5 text-xs text-destructive"
            >
              <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
              <p className="min-w-0 flex-1 break-words">
                <span className="font-medium">{err.title}:</span> {err.error}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
