import { Check, ImagePlus, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { resolveApiUrl } from "../services/api";
import type { TrackResponse } from "../types/music";

interface SourcesArtworkColumnProps {
  track: TrackResponse;
  onApplyCandidate: (source: string) => void;
  onSelectArtwork: (artworkId: string) => void;
  onUploadArtwork: (file: File) => void;
  onRefreshSearch: () => void;
  refreshing: boolean;
  uploading: boolean;
}

export function SourcesArtworkColumn({
  track,
  onApplyCandidate,
  onSelectArtwork,
  onUploadArtwork,
  onRefreshSearch,
  refreshing,
  uploading,
}: SourcesArtworkColumnProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [activeSource, setActiveSource] = useState<string>("");

  useEffect(() => {
    setActiveSource(track.metadata_candidates[0]?.source || "");
  }, [track.id, track.metadata_candidates]);

  const selectedCandidate =
    track.metadata_candidates.find((c) => c.source === activeSource) ||
    track.metadata_candidates[0] ||
    null;

  const triggerUpload = () => fileInputRef.current?.click();

  return (
    <section className="flex flex-col gap-5 rounded-2xl border border-border bg-card/70 p-5 backdrop-blur md:col-span-2 xl:col-span-1">
      {/* Metadata Sources Block */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Fuentes</h2>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {track.metadata_candidates.length} coincidencia
              {track.metadata_candidates.length === 1 ? "" : "s"}
            </span>
            <button
              type="button"
              onClick={onRefreshSearch}
              disabled={refreshing}
              title="Volver a buscar metadatos y carátulas con el título actual"
              className="cursor-pointer rounded-md p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40"
            >
              <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {track.metadata_candidates.length > 0 ? (
          <>
            <div className="flex flex-wrap gap-1.5">
              {track.metadata_candidates.map((cand) => {
                const isActive = cand.source === selectedCandidate?.source;
                return (
                  <button
                    key={cand.source}
                    type="button"
                    onClick={() => setActiveSource(cand.source)}
                    className={`cursor-pointer rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      isActive
                        ? "border-primary/50 bg-primary/10 font-medium text-primary"
                        : "border-border bg-background/40 text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {cand.source}
                  </button>
                );
              })}
            </div>

            {selectedCandidate && (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-border bg-background/50 p-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">
                    {selectedCandidate.title}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {selectedCandidate.artists.join(", ") || "—"}
                    {selectedCandidate.album ? ` · ${selectedCandidate.album}` : ""}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <div className="h-1 w-20 overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all"
                        style={{ width: `${Math.round(selectedCandidate.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {Math.round(selectedCandidate.confidence * 100)}%
                    </span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => onApplyCandidate(selectedCandidate.source)}
                  className="shrink-0 cursor-pointer rounded-lg bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground transition-colors hover:bg-accent"
                >
                  Aplicar
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-background/30 p-3 text-xs text-muted-foreground">
            Sin coincidencias externas todavía. Edita título/artista y pulsa actualizar para buscar.
          </div>
        )}
      </div>

      {/* Independent Artwork Grid Block */}
      <div className="flex flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Carátulas</h2>
          <button
            type="button"
            onClick={triggerUpload}
            disabled={uploading}
            className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
          >
            <ImagePlus className="size-3.5" />
            <span>{uploading ? "Subiendo..." : "Subir propia"}</span>
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onUploadArtwork(file);
            e.target.value = "";
          }}
        />

        <div className="grid grid-cols-3 gap-2.5">
          {track.artwork_candidates.slice(0, 5).map((art) => {
            const isSelected = art.id === track.selected_artwork_id || art.selected;
            const resolution =
              art.width && art.height ? `${art.width}×${art.height}` : art.format.toUpperCase();
            return (
              <button
                key={art.id}
                type="button"
                onClick={() => onSelectArtwork(art.id)}
                className={`group relative aspect-square cursor-pointer overflow-hidden rounded-xl bg-muted text-left transition-all ${
                  isSelected
                    ? "border-2 border-primary shadow-[0_0_0_2px_oklch(88%_0.19_128/0.18)]"
                    : "border border-border hover:border-foreground/30"
                }`}
              >
                <img
                  src={resolveApiUrl(art.url)}
                  alt={`Carátula ${art.source}`}
                  loading="lazy"
                  className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
                />

                {isSelected && (
                  <span className="absolute top-1.5 right-1.5 flex size-5 items-center justify-center rounded-full bg-primary text-primary-foreground shadow">
                    <Check className="size-3 stroke-[3]" />
                  </span>
                )}

                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/45 to-transparent px-2 pt-5 pb-1.5">
                  <p className="truncate text-[11px] font-medium text-white">{art.source}</p>
                  <p className="font-mono text-[9px] text-white/75">{resolution}</p>
                </div>
              </button>
            );
          })}

          <button
            type="button"
            onClick={triggerUpload}
            disabled={uploading}
            className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-input bg-background/30 text-muted-foreground transition-colors hover:border-foreground/40 hover:bg-background/50 hover:text-foreground disabled:opacity-40"
          >
            <Plus className="size-4" />
            <span className="text-[11px]">Subir</span>
          </button>
        </div>
      </div>
    </section>
  );
}
