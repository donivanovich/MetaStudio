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

  // Single-line sliding window of 13 dots (active dot stays centered from track 7 until the last 7 tracks)
  const WINDOW_SIZE = 13;
  const HALF_WINDOW = Math.floor(WINDOW_SIZE / 2); // 6 -> 7th dot is exact center
  const maxStart = Math.max(0, tracks.length - WINDOW_SIZE);
  const windowStart = Math.max(0, Math.min(currentIndex - HALF_WINDOW, maxStart));
  const windowEnd = Math.min(tracks.length, windowStart + WINDOW_SIZE);
  const visibleTracks = tracks.slice(windowStart, windowEnd);
  const hasMoreLeft = windowStart > 0;
  const hasMoreRight = windowEnd < tracks.length;

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

        <div className="flex flex-nowrap items-center justify-center gap-1.5">
          {visibleTracks.map((t, offset) => {
            const idx = windowStart + offset;
            const isActive = idx === currentIndex;
            const isEdgeFade =
              !isActive &&
              ((offset === 0 && hasMoreLeft) ||
                (offset === visibleTracks.length - 1 && hasMoreRight));
            const sizeClass = isActive
              ? "h-1.5 w-5"
              : isEdgeFade
                ? "size-1"
                : "size-1.5";
            const colorClass = isActive
              ? "bg-primary"
              : t.status === "error"
                ? "bg-destructive"
                : t.status === "ready" || t.status === "downloaded"
                  ? "bg-foreground/50"
                  : "bg-foreground/20";

            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onSelectIndex(idx)}
                title={`${idx + 1}. ${t.title} (${t.status})`}
                aria-label={`Ir a canción ${idx + 1}: ${t.title}`}
                className={`shrink-0 cursor-pointer rounded-full transition-all duration-150 hover:opacity-90 ${sizeClass} ${colorClass}`}
              />
            );
          })}
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
