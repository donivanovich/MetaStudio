import {
  Download,
  FolderArchive,
  ListX,
  Loader2,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { resolveApiUrl } from "../services/api";
import type { TrackResponse } from "../types/music";

interface ActionFooterProps {
  track: TrackResponse;
  queueCount: number;
  isBusyDownloading: boolean;
  onToggleQueue: () => void;
  onClearQueue: () => void;
  onRetryTrack: () => void;
  onDownloadSingle: () => void;
  onDownloadPlaylist: () => void;
}

export function ActionFooter({
  track,
  queueCount,
  isBusyDownloading,
  onToggleQueue,
  onClearQueue,
  onRetryTrack,
  onDownloadSingle,
  onDownloadPlaylist,
}: ActionFooterProps) {
  const canDownloadSingle = track.audio_downloadable && track.status !== "processing" && !isBusyDownloading;

  return (
    <footer className="mt-auto flex flex-col-reverse gap-3 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onToggleQueue}
          className={`inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors ${
            track.in_queue
              ? "border-border bg-card/70 text-muted-foreground hover:border-destructive/40 hover:text-destructive"
              : "border-primary/40 bg-primary/10 text-primary hover:bg-primary/20"
          }`}
        >
          {track.in_queue ? (
            <>
              <Trash2 className="size-4" />
              <span>Quitar de la cola</span>
            </>
          ) : (
            <>
              <RotateCcw className="size-4" />
              <span>Volver a la cola</span>
            </>
          )}
        </button>

        {queueCount > 0 && (
          <button
            type="button"
            disabled={isBusyDownloading}
            onClick={onClearQueue}
            className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-border bg-card/70 px-4 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-45"
          >
            <ListX className="size-4" />
            <span>Limpiar cola</span>
          </button>
        )}

        {track.status === "error" && (
          <button
            type="button"
            onClick={onRetryTrack}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/20"
          >
            <RotateCcw className="size-3.5" />
            <span>Reintentar pista</span>
          </button>
        )}

        {track.download_url && (
          <a
            href={resolveApiUrl(track.download_url)}
            download={track.downloaded_file_name || undefined}
            className="inline-flex items-center gap-1.5 rounded-xl border border-primary/40 bg-primary/10 px-3.5 py-2.5 font-mono text-xs text-primary transition-colors hover:bg-primary/20"
          >
            <Download className="size-3.5" />
            <span>{track.downloaded_file_name}</span>
          </a>
        )}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {queueCount > 1 && (
          <button
            type="button"
            disabled={isBusyDownloading}
            onClick={onDownloadPlaylist}
            className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-border bg-secondary px-4 py-2.5 text-sm font-medium text-secondary-foreground transition-colors hover:bg-accent disabled:cursor-not-allowed disabled:opacity-45"
          >
            <FolderArchive className="size-4" />
            <span>Descargar playlist ({queueCount})</span>
          </button>
        )}

        <button
          type="button"
          disabled={!canDownloadSingle}
          onClick={onDownloadSingle}
          className="inline-flex min-w-[240px] cursor-pointer items-center justify-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-[0_10px_40px_-10px_var(--primary)] transition-all hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none"
        >
          {isBusyDownloading || track.status === "downloading" ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Download className="size-4" />
          )}
          <span>
            {track.status === "downloading"
              ? `Descargando ${Math.round(track.download_progress)}%`
              : "Descargar canción"}
          </span>
        </button>
      </div>
    </footer>
  );
}
