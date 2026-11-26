import {
  ChevronLeft,
  ChevronRight,
  Disc3,
  Pause,
  Play,
  SkipBack,
  SkipForward,
  VolumeX,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { resolveApiUrl } from "../services/api";
import type { TrackResponse } from "../types/music";

interface PlayerColumnProps {
  track: TrackResponse;
  hasPrev: boolean;
  hasNext: boolean;
  onPrevTrack: () => void;
  onNextTrack: () => void;
  onSelectArtwork: (artworkId: string) => void;
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || !Number.isFinite(seconds) || seconds < 0) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function PlayerColumn({
  track,
  hasPrev,
  hasNext,
  onPrevTrack,
  onNextTrack,
  onSelectArtwork,
}: PlayerColumnProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [audioDuration, setAudioDuration] = useState<number | null>(null);
  const [audioError, setAudioError] = useState(false);

  const artworks = track.artwork_candidates;
  const activeArtIdx = Math.max(
    0,
    artworks.findIndex((a) => a.id === track.selected_artwork_id || a.selected),
  );
  const activeArt = artworks[activeArtIdx] || null;
  const coverUrl = resolveApiUrl(activeArt?.url || track.selected_artwork_url);

  // Reset player cleanly when switching tracks or preview URL changes
  useEffect(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    setIsPlaying(false);
    setCurrentTime(0);
    setAudioDuration(null);
    setAudioError(false);
  }, [track.id, track.preview_audio_url]);

  const togglePlay = async () => {
    const audio = audioRef.current;
    if (!audio || !track.preview_audio_url) return;
    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      try {
        setAudioError(false);
        await audio.play();
        setIsPlaying(true);
      } catch {
        setAudioError(true);
        setIsPlaying(false);
      }
    }
  };

  const handleSeek = (value: number) => {
    const audio = audioRef.current;
    if (audio && Number.isFinite(value)) {
      audio.currentTime = value;
      setCurrentTime(value);
    }
  };

  const cycleArtwork = (delta: number) => {
    if (artworks.length <= 1) return;
    const nextIdx = (activeArtIdx + delta + artworks.length) % artworks.length;
    onSelectArtwork(artworks[nextIdx].id);
  };

  const displayDuration = audioDuration || track.duration_seconds || 0;

  return (
    <section className="flex flex-col rounded-2xl border border-border bg-card/70 p-5 backdrop-blur">
      {/* Square Artwork Preview + Carousel Arrows */}
      <div className="group relative aspect-square w-full overflow-hidden rounded-xl bg-muted shadow-2xl">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={`Carátula de ${track.title}`}
            className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.015]"
          />
        ) : (
          <div className="flex size-full flex-col items-center justify-center gap-2 text-muted-foreground">
            <Disc3 className="size-14 opacity-40" />
            <span className="text-xs">Sin carátula</span>
          </div>
        )}

        {artworks.length > 1 && (
          <>
            <button
              type="button"
              onClick={() => cycleArtwork(-1)}
              aria-label="Carátula anterior"
              className="absolute top-1/2 left-2.5 flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full bg-background/75 text-foreground opacity-0 backdrop-blur transition-opacity hover:bg-background group-hover:opacity-100"
            >
              <ChevronLeft className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => cycleArtwork(1)}
              aria-label="Carátula siguiente"
              className="absolute top-1/2 right-2.5 flex size-8 -translate-y-1/2 cursor-pointer items-center justify-center rounded-full bg-background/75 text-foreground opacity-0 backdrop-blur transition-opacity hover:bg-background group-hover:opacity-100"
            >
              <ChevronRight className="size-4" />
            </button>
          </>
        )}
      </div>

      {/* Artwork Source Indicator Dots */}
      <div className="mt-3.5 flex items-center justify-center gap-1.5">
        {artworks.slice(0, 6).map((art, idx) => (
          <button
            key={art.id}
            type="button"
            onClick={() => onSelectArtwork(art.id)}
            aria-label={`Carátula ${art.source}`}
            title={art.source}
            className={`h-1.5 cursor-pointer rounded-full transition-all ${
              idx === activeArtIdx ? "w-6 bg-primary" : "w-2 bg-foreground/20 hover:bg-foreground/40"
            }`}
          />
        ))}
      </div>

      {/* Live Metadata Preview */}
      <div className="mt-4 min-w-0">
        <h2 className="truncate text-xl font-semibold tracking-tight text-foreground">
          {track.title || "Sin título"}
        </h2>
        <p className="mt-0.5 truncate text-sm text-muted-foreground">
          {track.artists_display || "Artista desconocido"}
        </p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground/70">
          {track.album || track.title}
        </p>
      </div>

      {/* Authorized Preview Audio Element (never downloads full MP3 automatically) */}
      {track.preview_audio_url && (
        <audio
          ref={audioRef}
          src={track.preview_audio_url}
          preload="none"
          onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => setAudioDuration(e.currentTarget.duration)}
          onEnded={() => setIsPlaying(false)}
          onError={() => {
            setAudioError(true);
            setIsPlaying(false);
          }}
        />
      )}

      {/* Progress Scrubber */}
      <div className="mt-5">
        <input
          type="range"
          min={0}
          max={displayDuration || 100}
          step={0.5}
          value={Math.min(currentTime, displayDuration || 100)}
          disabled={!track.preview_audio_url}
          onChange={(e) => handleSeek(Number(e.target.value))}
          aria-label="Progreso de previsualización"
          className="studio-range w-full disabled:cursor-not-allowed disabled:opacity-40"
        />
        <div className="mt-1.5 flex items-center justify-between font-mono text-[11px] text-muted-foreground">
          <span>{formatDuration(currentTime)}</span>
          {audioError ? (
            <span className="inline-flex items-center gap-1 font-sans text-[11px] text-muted-foreground/80">
              <VolumeX className="size-3" /> Previsualización no disponible
            </span>
          ) : !track.preview_audio_url ? (
            <span className="font-sans text-[11px] text-muted-foreground/70">
              Sin previsualización autorizada
            </span>
          ) : null}
          <span>{formatDuration(displayDuration)}</span>
        </div>
      </div>

      {/* Transport Controls */}
      <div className="mt-3 flex items-center justify-center gap-6">
        <button
          type="button"
          onClick={onPrevTrack}
          disabled={!hasPrev}
          aria-label="Canción anterior"
          className="cursor-pointer p-2 text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
        >
          <SkipBack className="size-5" />
        </button>

        <button
          type="button"
          onClick={togglePlay}
          disabled={!track.preview_audio_url}
          aria-label={isPlaying ? "Pausar previsualización" : "Reproducir previsualización"}
          className="flex size-12 cursor-pointer items-center justify-center rounded-full bg-foreground text-background shadow-lg transition-transform hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-35"
        >
          {isPlaying ? <Pause className="size-5 fill-current" /> : <Play className="ml-0.5 size-5 fill-current" />}
        </button>

        <button
          type="button"
          onClick={onNextTrack}
          disabled={!hasNext}
          aria-label="Canción siguiente"
          className="cursor-pointer p-2 text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30"
        >
          <SkipForward className="size-5" />
        </button>
      </div>
    </section>
  );
}
