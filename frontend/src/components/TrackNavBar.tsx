import { ChevronLeft, ChevronRight } from "lucide-react";
import type { TrackResponse } from "../types/music";

interface TrackNavBarProps {
  tracks: TrackResponse[];
  currentIndex: number;
  processedCount: number;
  onSelectIndex: (index: number) => void;
}

export function TrackNavBar({
  tracks,
  currentIndex,
  processedCount,
  onSelectIndex,
}: TrackNavBarProps) {
  if (tracks.length === 0) return null;

  const prevTrack = currentIndex > 0 ? tracks[currentIndex - 1] : null;
  const nextTrack = currentIndex < tracks.length - 1 ? tracks[currentIndex + 1] : null;

  return (
    <nav
      aria-label="Navegación entre canciones"
      className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-3 rounded-2xl border border-border bg-card/70 px-3 py-2.5 backdrop-blur"
    >
      <button
        type="button"
        disabled={!prevTrack}
        onClick={() => prevTrack && onSelectIndex(currentIndex - 1)}
        className="group flex min-w-0 cursor-pointer items-center gap-3 text-left transition-opacity disabled:cursor-not-allowed disabled:opacity-30"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background/40 text-foreground transition-colors group-hover:bg-accent">
          <ChevronLeft className="size-4" />
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Anterior
          </span>
          <span className="block truncate text-sm text-foreground">
            {prevTrack ? prevTrack.title : "—"}
          </span>
        </span>
      </button>

      <div className="flex flex-col items-center gap-1.5">
        <div className="font-mono text-sm">
          <span className="font-semibold text-foreground">{currentIndex + 1}</span>
          <span className="mx-1.5 text-muted-foreground">/</span>
          <span className="text-muted-foreground">{tracks.length}</span>
        </div>

        <div className="flex max-w-[240px] flex-wrap items-center justify-center gap-1">
          {tracks.slice(0, 36).map((t, idx) => {
            const isActive = idx === currentIndex;
            const dotClass = isActive
              ? "h-1.5 w-5 bg-primary"
              : t.status === "error"
                ? "h-1.5 w-1.5 bg-destructive"
                : t.status === "ready" || t.status === "downloaded"
                  ? "h-1.5 w-1.5 bg-foreground/50"
                  : "h-1.5 w-1.5 bg-foreground/15";

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onSelectIndex(idx)}
                title={`${idx + 1}. ${t.title} (${t.status})`}
                aria-label={`Ir a canción ${idx + 1}: ${t.title}`}
                className={`cursor-pointer rounded-full transition-all hover:opacity-90 ${dotClass}`}
              />
            );
          })}
          {tracks.length > 36 && (
            <span className="font-mono text-[10px] text-muted-foreground">
              +{tracks.length - 36}
            </span>
          )}
        </div>

        <span className="text-[11px] text-muted-foreground">
          {processedCount} procesada{processedCount === 1 ? "" : "s"}
        </span>
      </div>

      <button
        type="button"
        disabled={!nextTrack}
        onClick={() => nextTrack && onSelectIndex(currentIndex + 1)}
        className="group flex min-w-0 cursor-pointer items-center justify-end gap-3 text-right transition-opacity disabled:cursor-not-allowed disabled:opacity-30"
      >
        <span className="hidden min-w-0 sm:block">
          <span className="block text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Siguiente
          </span>
          <span className="block truncate text-sm text-foreground">
            {nextTrack ? nextTrack.title : "—"}
          </span>
        </span>
        <span className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-border bg-background/40 text-foreground transition-colors group-hover:bg-accent">
          <ChevronRight className="size-4" />
        </span>
      </button>
    </nav>
  );
}
