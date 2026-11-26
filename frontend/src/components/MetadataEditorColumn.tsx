import { Plus, Sparkles, X } from "lucide-react";
import { useMemo, useState } from "react";
import type { TagCatalogResponse, TagDefinition, TrackResponse } from "../types/music";

interface MetadataEditorColumnProps {
  track: TrackResponse;
  catalog: TagCatalogResponse | null;
  onTitleChange: (value: string) => void;
  onArtistsTextChange: (value: string) => void;
  onAlbumChange: (value: string) => void;
  onTagsChange: (tagIds: string[]) => void;
  onCreateCustomTag: (category: "language" | "mood", name: string) => Promise<TagDefinition | null>;
}

export function MetadataEditorColumn({
  track,
  catalog,
  onTitleChange,
  onArtistsTextChange,
  onAlbumChange,
  onTagsChange,
  onCreateCustomTag,
}: MetadataEditorColumnProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [newCategory, setNewCategory] = useState<"mood" | "language">("mood");
  const [newTagName, setNewTagName] = useState("");
  const [creating, setCreating] = useState(false);

  const tagMap = useMemo(() => {
    const map = new Map<string, TagDefinition>();
    if (!catalog) return map;
    for (const t of catalog.languages) map.set(t.id, t);
    for (const t of catalog.moods) map.set(t.id, t);
    return map;
  }, [catalog]);

  const toggleTag = (tagId: string) => {
    const exists = track.selected_tag_ids.includes(tagId);
    const updated = exists
      ? track.selected_tag_ids.filter((id) => id !== tagId)
      : [...track.selected_tag_ids, tagId];
    onTagsChange(updated);
  };

  const handleCreate = async () => {
    if (!newTagName.trim() || creating) return;
    setCreating(true);
    try {
      const created = await onCreateCustomTag(newCategory, newTagName.trim());
      if (created && !track.selected_tag_ids.includes(created.id)) {
        onTagsChange([...track.selected_tag_ids, created.id]);
      }
      setNewTagName("");
    } finally {
      setCreating(false);
    }
  };

  const unappliedSuggestions = track.suggested_tags.filter(
    (s) => !track.selected_tag_ids.includes(s.tag_id),
  );

  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-border bg-card/70 p-5 backdrop-blur">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Metadatos</h2>
        <span
          className="rounded-md bg-secondary px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
          title="Exportación estricta de 4 frames ID3v2.3: TIT2, TPE1, TALB, APIC"
        >
          ID3v2.3
        </span>
      </div>

      {/* ONLY the 3 editable text fields (4th field is Artwork) */}
      <div className="flex flex-col gap-4">
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label
              htmlFor="meta-title"
              className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground"
            >
              Nombre de la canción
            </label>
            {track.metadata_provenance.title && (
              <span className="font-mono text-[10px] text-muted-foreground/70">
                {track.metadata_provenance.title}
              </span>
            )}
          </div>
          <input
            id="meta-title"
            type="text"
            value={track.title}
            onChange={(e) => onTitleChange(e.target.value)}
            className="w-full rounded-xl border border-input bg-background/60 px-3.5 py-2.5 text-sm text-foreground transition-colors focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label
              htmlFor="meta-artists"
              className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground"
            >
              Artistas
            </label>
            {track.metadata_provenance.artists && (
              <span className="font-mono text-[10px] text-muted-foreground/70">
                {track.metadata_provenance.artists}
              </span>
            )}
          </div>
          <input
            id="meta-artists"
            type="text"
            value={track.artists_display}
            onChange={(e) => onArtistsTextChange(e.target.value)}
            className="w-full rounded-xl border border-input bg-background/60 px-3.5 py-2.5 text-sm text-foreground transition-colors focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
          <p className="mt-1.5 text-[11px] text-muted-foreground/80">
            Separados por coma y espacio · ej. Bad Bunny, Feid
          </p>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label
              htmlFor="meta-album"
              className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground"
            >
              Álbum
            </label>
            <span className="font-mono text-[10px] text-muted-foreground/70">
              {track.album_auto_synced
                ? "auto · título"
                : track.metadata_provenance.album || "manual"}
            </span>
          </div>
          <input
            id="meta-album"
            type="text"
            value={track.album}
            onChange={(e) => onAlbumChange(e.target.value)}
            placeholder={track.title}
            className="w-full rounded-xl border border-input bg-background/60 px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/50 transition-colors focus:border-primary/60 focus:outline-none focus:ring-2 focus:ring-ring/40"
          />
        </div>
      </div>

      {/* Independent Smart Tags Section (NOT exported to MP3 ID3) */}
      <div className="mt-2 border-t border-border pt-4">
        <div className="mb-2.5 flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            Etiquetas
          </span>
          {track.suggested_tags.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <Sparkles className="size-3 text-primary" />
              detectadas
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {track.selected_tag_ids.map((tagId) => {
            const def = tagMap.get(tagId);
            const isLang = (def?.category || (tagId.startsWith("lang.") ? "language" : "mood")) === "language";
            const label = def?.display_name || tagId.split(".")[1] || tagId;
            return (
              <span
                key={tagId}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
                  isLang
                    ? "border-lang/40 bg-lang/10 text-lang"
                    : "border-mood/40 bg-mood/10 text-mood"
                }`}
              >
                <span
                  className={`size-1.5 rounded-full ${isLang ? "bg-lang" : "bg-mood"}`}
                />
                <span>{label}</span>
                <button
                  type="button"
                  onClick={() => toggleTag(tagId)}
                  aria-label={`Quitar etiqueta ${label}`}
                  className="ml-0.5 cursor-pointer opacity-70 transition-opacity hover:opacity-100"
                >
                  <X className="size-3" />
                </button>
              </span>
            );
          })}

          <button
            type="button"
            onClick={() => setPickerOpen((v) => !v)}
            className="inline-flex cursor-pointer items-center gap-1 rounded-full border border-dashed border-input px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/40 hover:text-foreground"
          >
            <Plus className="size-3" />
            <span>Añadir</span>
          </button>
        </div>

        {/* Unapplied smart suggestions */}
        {unappliedSuggestions.length > 0 && (
          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground/75">Sugeridas:</span>
            {unappliedSuggestions.map((s) => (
              <button
                key={s.tag_id}
                type="button"
                onClick={() => toggleTag(s.tag_id)}
                title={s.rationale || `${Math.round(s.confidence * 100)}% (${s.source})`}
                className="cursor-pointer rounded-full border border-border bg-secondary/50 px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
              >
                + {s.display_name}
              </button>
            ))}
          </div>
        )}

        {/* Inline Catalog Picker */}
        {pickerOpen && catalog && (
          <div className="mt-3 space-y-3 rounded-xl border border-border bg-background/50 p-3">
            <div>
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Idiomas
              </p>
              <div className="flex flex-wrap gap-1.5">
                {catalog.languages.map((tag) => {
                  const active = track.selected_tag_ids.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => toggleTag(tag.id)}
                      className={`cursor-pointer rounded-full border px-2.5 py-0.5 text-[11px] transition-colors ${
                        active
                          ? "border-lang/50 bg-lang/15 text-lang"
                          : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {tag.display_name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Estados de ánimo
              </p>
              <div className="flex flex-wrap gap-1.5">
                {catalog.moods.map((tag) => {
                  const active = track.selected_tag_ids.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => toggleTag(tag.id)}
                      className={`cursor-pointer rounded-full border px-2.5 py-0.5 text-[11px] transition-colors ${
                        active
                          ? "border-mood/50 bg-mood/15 text-mood"
                          : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {tag.display_name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center gap-1.5 border-t border-border pt-2.5">
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value as "mood" | "language")}
                className="rounded-lg border border-input bg-card px-2 py-1 text-xs text-foreground focus:outline-none"
                aria-label="Categoría de nueva etiqueta"
              >
                <option value="mood">Ánimo</option>
                <option value="language">Idioma</option>
              </select>
              <input
                type="text"
                value={newTagName}
                onChange={(e) => setNewTagName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleCreate())}
                placeholder="Nueva etiqueta"
                className="min-w-0 flex-1 rounded-lg border border-input bg-card px-2.5 py-1 text-xs text-foreground placeholder:text-muted-foreground/60 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleCreate}
                disabled={!newTagName.trim() || creating}
                className="cursor-pointer rounded-lg bg-secondary px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent disabled:opacity-40"
              >
                Crear
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
