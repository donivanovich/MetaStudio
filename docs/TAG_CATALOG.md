# Catálogo de Etiquetas Inteligentes (v1.0.0)

## Propósito

El sistema de etiquetas de **MetaStudio** está diseñado como un módulo **independiente y reutilizable** para futuras aplicaciones web, móviles o de escritorio.

> **Regla fundamental:** Las etiquetas de idioma y estado de ánimo **nunca** se escriben como campos ID3 en los archivos MP3 exportados. Se almacenan aparte usando identificadores estables y versionados.

---

## Estructura del Catálogo (`catalog_version: "1.0.0"`)

Cada etiqueta tiene:
- `id`: Identificador estable inmutable (`lang.<codigo>` o `mood.<slug>`).
- `category`: `"language"` | `"mood"`.
- `name`: Nombre canónico normalizado.
- `display_name`: Etiqueta visual para interfaz.
- `aliases`: Lista de sinónimos/códigos ISO para mapeo desde fuentes externas.

### Categoría: Idioma (`language`)

| ID estable | Nombre | Aliases / Códigos ISO |
| --- | --- | --- |
| `lang.es` | Spanish | `es`, `spa`, `spanish`, `español`, `castellano` |
| `lang.en` | English | `en`, `eng`, `english`, `inglés` |
| `lang.fr` | French | `fr`, `fra`, `fre`, `french`, `francés` |
| `lang.pt` | Portuguese | `pt`, `por`, `portuguese`, `portugués` |
| `lang.it` | Italian | `it`, `ita`, `italian`, `italiano` |
| `lang.de` | German | `de`, `deu`, `ger`, `german`, `alemán` |
| `lang.ja` | Japanese | `ja`, `jpn`, `japanese`, `japonés` |
| `lang.ko` | Korean | `ko`, `kor`, `korean`, `coreano` |
| `lang.instrumental` | Instrumental | `zxx`, `instrumental`, `inst` |
| `lang.unknown` | Unknown | `und`, `unknown`, `desconocido` |

### Categoría: Estado de Ánimo (`mood`)

| ID estable | Nombre |
| --- | --- |
| `mood.sad` | Sad |
| `mood.hype` | Hype |
| `mood.chill` | Chill |
| `mood.happy` | Happy |
| `mood.romantic` | Romantic |
| `mood.energetic` | Energetic |
| `mood.melancholic` | Melancholic |
| `mood.aggressive` | Aggressive |
| `mood.relaxed` | Relaxed |
| `mood.dark` | Dark |
| `mood.nostalgic` | Nostalgic |

---

## Fuentes de Detección e Inferencia

1. **Metadatos originales de archivo / extracción** (`TCON` género, `TLAN` idioma, etiquetas de extracción `yt-dlp`).
2. **Proveedores musicales** (género principal de iTunes/Deezer, tags comunitarios de MusicBrainz, estilos de Discogs).
3. **Heurísticas ponderadas con umbral de confianza**:
   - Cada sugerencia devuelve `{ tag_id, category, confidence, source, rationale }`.
   - Si una señal no alcanza el umbral mínimo de confianza (`>= 0.55`), no se inventa la etiqueta.
   - No se asignan automáticamente todos los posibles estados de ánimo de un género; se priorizan las coincidencias más específicas (p. ej. `Sad Trap` → `mood.sad`, `mood.melancholic`, limitado a sugerencias con mayor soporte).
   - El idioma no se asume únicamente por el idioma del título si existe `TLAN` o información explícita de proveedor.

## Persistencia Independiente

Las asignaciones confirmadas/editadas por el usuario se guardan en JSON estructurado (`backend/data/track_tags.json`) indexadas por huella estable de pista (`source_url` / `track_key`), permitiendo exportarlas e importarlas en futuras apps de escritorio o móvil.
