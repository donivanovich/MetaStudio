import { Sparkles } from "lucide-react";
import { BrandLogo } from "./BrandLogo";

interface EmptyStateProps {
  onFillExampleUrl: (url: string) => void;
}

export function EmptyState({ onFillExampleUrl }: EmptyStateProps) {
  return (
    <div className="my-auto flex flex-col items-center justify-center py-12">
      <div className="flex max-w-md flex-col items-center rounded-2xl border border-border bg-card/70 px-8 py-10 text-center backdrop-blur">
        <div className="mb-4 rounded-2xl shadow-[0_10px_30px_-10px_var(--primary)]">
          <BrandLogo className="size-14" />
        </div>
        <h2 className="text-lg font-semibold tracking-tight text-foreground">
          Empieza pegando un enlace
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          Introduce la URL de una canción o playlist compatible en la barra superior. Analizaremos
          las pistas con carga diferida para que revises los 4 campos ID3, carátulas y etiquetas
          antes de exportar a MP3.
        </p>

        <div className="mt-5 flex flex-wrap justify-center gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full border border-border bg-background/50 px-2.5 py-1">
            Solo 4 campos ID3v2.3
          </span>
          <span className="rounded-full border border-border bg-background/50 px-2.5 py-1">
            Lazy loading de playlists
          </span>
          <span className="rounded-full border border-border bg-background/50 px-2.5 py-1">
            Etiquetas separadas del MP3
          </span>
        </div>

        <button
          type="button"
          onClick={() =>
            onFillExampleUrl("https://www.youtube.com/watch?v=aqz-KE-bpKQ")
          }
          className="mt-6 inline-flex cursor-pointer items-center gap-2 rounded-xl border border-border bg-secondary px-4 py-2 text-xs font-medium text-foreground transition-colors hover:bg-accent"
        >
          <Sparkles className="size-3.5 text-primary" />
          <span>Rellenar enlace de prueba</span>
        </button>
      </div>
    </div>
  );
}
