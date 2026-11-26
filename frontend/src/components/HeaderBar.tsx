import { Link2, ListMusic, Loader2, Sparkles } from "lucide-react";
import type { FormEvent } from "react";
import { BrandLogo } from "./BrandLogo";

interface HeaderBarProps {
  url: string;
  onUrlChange: (value: string) => void;
  onAnalyze: () => void;
  analyzing: boolean;
  queueCount: number;
  ffmpegAvailable: boolean | null;
}

const PLATFORMS = ["YT Music", "YouTube", "SoundCloud"];

export function HeaderBar({
  url,
  onUrlChange,
  onAnalyze,
  analyzing,
  queueCount,
  ffmpegAvailable,
}: HeaderBarProps) {
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!url.trim() || analyzing) return;
    onAnalyze();
  };

  return (
    <header className="grid gap-4 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-center lg:gap-10">
      <div className="flex items-center gap-3">
        <div className="shrink-0 rounded-xl shadow-[0_6px_24px_-8px_var(--primary)]">
          <BrandLogo className="size-10" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-semibold tracking-tight text-foreground">
              Meta<span className="text-primary">Studio</span>
            </h1>
            {ffmpegAvailable === false && (
              <span className="rounded-md border border-destructive/40 bg-destructive/15 px-1.5 py-0.5 font-mono text-[10px] text-destructive">
                FFmpeg off
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">Metadatos ID3 precisos</p>
        </div>
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 rounded-2xl border border-border bg-card p-1.5 pl-4 transition-shadow focus-within:ring-2 focus-within:ring-ring"
      >
        <Link2 className="size-4 shrink-0 text-muted-foreground" />
        <input
          type="url"
          value={url}
          onChange={(e) => onUrlChange(e.target.value)}
          placeholder="Pega un enlace de YouTube, YouTube Music o playlist..."
          className="min-w-0 flex-1 bg-transparent font-mono text-sm text-foreground placeholder:font-sans placeholder:text-muted-foreground/70 focus:outline-none"
          aria-label="URL de canción o playlist"
        />

        <div className="hidden items-center gap-1.5 lg:flex">
          {PLATFORMS.map((label) => (
            <span
              key={label}
              className="rounded-md border border-border bg-secondary/70 px-2 py-0.5 text-[11px] text-muted-foreground"
            >
              {label}
            </span>
          ))}
        </div>

        {queueCount > 0 && (
          <div
            className="hidden items-center gap-1.5 rounded-xl border border-border bg-secondary px-2.5 py-1.5 font-mono text-xs text-foreground sm:flex"
            title="Canciones en la cola de descarga"
          >
            <ListMusic className="size-3.5 text-muted-foreground" />
            <span>{queueCount}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={!url.trim() || analyzing}
          className="inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-all hover:brightness-105 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-45"
        >
          {analyzing ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Sparkles className="size-4" />
          )}
          <span>{analyzing ? "Extrayendo..." : "Extraer"}</span>
        </button>
      </form>
    </header>
  );
}
