"""Centralized, versioned tag catalog for Language and Mood (reusable across future apps)."""

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from backend.config.settings import get_settings

CATALOG_VERSION = "1.0.0"


@dataclass(frozen=True)
class TagDefinition:
    """Stable catalog entry for a language or mood tag."""

    id: str
    category: str  # "language" | "mood"
    name: str
    display_name: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    custom: bool = False

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["aliases"] = list(self.aliases)
        return data


BUILTIN_LANGUAGE_TAGS: tuple[TagDefinition, ...] = (
    TagDefinition("lang.es", "language", "Spanish", "Español", ("es", "spa", "spanish", "español", "castellano")),
    TagDefinition("lang.en", "language", "English", "Inglés", ("en", "eng", "english", "inglés")),
    TagDefinition("lang.fr", "language", "French", "Francés", ("fr", "fra", "fre", "french", "francés")),
    TagDefinition("lang.pt", "language", "Portuguese", "Portugués", ("pt", "por", "portuguese", "portugués")),
    TagDefinition("lang.it", "language", "Italian", "Italiano", ("it", "ita", "italian", "italiano")),
    TagDefinition("lang.de", "language", "German", "Alemán", ("de", "deu", "ger", "german", "alemán")),
    TagDefinition("lang.ja", "language", "Japanese", "Japonés", ("ja", "jpn", "japanese", "japonés")),
    TagDefinition("lang.ko", "language", "Korean", "Coreano", ("ko", "kor", "korean", "coreano")),
    TagDefinition("lang.instrumental", "language", "Instrumental", "Instrumental", ("zxx", "instrumental", "inst")),
    TagDefinition("lang.unknown", "language", "Unknown", "Desconocido", ("und", "unknown", "desconocido")),
)

BUILTIN_MOOD_TAGS: tuple[TagDefinition, ...] = (
    TagDefinition("mood.sad", "mood", "Sad", "Sad", ("sad", "triste", "heartbreak", "depressing")),
    TagDefinition("mood.hype", "mood", "Hype", "Hype", ("hype", "party", "club", "banger", "turn up")),
    TagDefinition("mood.chill", "mood", "Chill", "Chill", ("chill", "chillout", "smooth", "laid-back", "mellow")),
    TagDefinition("mood.happy", "mood", "Happy", "Happy", ("happy", "upbeat", "joyful", "feel-good", "cheerful")),
    TagDefinition("mood.romantic", "mood", "Romantic", "Romantic", ("romantic", "love", "sensual", "intimate")),
    TagDefinition("mood.energetic", "mood", "Energetic", "Energetic", ("energetic", "workout", "high-energy", "intense")),
    TagDefinition("mood.melancholic", "mood", "Melancholic", "Melancholic", ("melancholic", "melancholy", "bittersweet", "wistful")),
    TagDefinition("mood.aggressive", "mood", "Aggressive", "Aggressive", ("aggressive", "angry", "hardcore", "heavy", "rage")),
    TagDefinition("mood.relaxed", "mood", "Relaxed", "Relaxed", ("relaxed", "calm", "peaceful", "soothing", "ambient")),
    TagDefinition("mood.dark", "mood", "Dark", "Dark", ("dark", "moody", "ominous", "brooding", "noir")),
    TagDefinition("mood.nostalgic", "mood", "Nostalgic", "Nostalgic", ("nostalgic", "retro", "throwback", "vintage")),
)


class TagCatalog:
    """Versioned, extensible tag registry independent from download and ID3 layers."""

    def __init__(self) -> None:
        self._builtin: dict[str, TagDefinition] = {
            t.id: t for t in (*BUILTIN_LANGUAGE_TAGS, *BUILTIN_MOOD_TAGS)
        }

    def _custom_file(self):
        return get_settings().data_path / "custom_tags.json"

    def _load_custom_tags(self) -> dict[str, TagDefinition]:
        path = self._custom_file()
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            loaded: dict[str, TagDefinition] = {}
            for item in raw.get("tags", []):
                tag = TagDefinition(
                    id=str(item["id"]),
                    category=str(item["category"]),
                    name=str(item["name"]),
                    display_name=str(item.get("display_name") or item["name"]),
                    aliases=tuple(item.get("aliases") or ()),
                    custom=True,
                )
                loaded[tag.id] = tag
            return loaded
        except Exception:
            return {}

    def all_tags(self) -> dict[str, TagDefinition]:
        merged = dict(self._builtin)
        merged.update(self._load_custom_tags())
        return merged

    def get(self, tag_id: str) -> TagDefinition | None:
        return self.all_tags().get(tag_id)

    def resolve_language_alias(self, raw_value: str) -> TagDefinition | None:
        cleaned = (raw_value or "").strip().lower()
        if not cleaned:
            return None
        # Handle locale codes like "es-ES" or "en_US"
        primary = re.split(r"[-_]", cleaned)[0]
        for tag in self.all_tags().values():
            if tag.category != "language":
                continue
            if cleaned == tag.id or cleaned == tag.name.lower() or primary in tag.aliases or cleaned in tag.aliases:
                return tag
        return None

    def register_custom_tag(self, *, category: str, name: str) -> TagDefinition:
        if category not in {"language", "mood"}:
            raise ValueError("La categoría debe ser 'language' o 'mood'.")
        clean_name = name.strip()
        if not clean_name or len(clean_name) > 40:
            raise ValueError("El nombre de la etiqueta debe tener entre 1 y 40 caracteres.")

        slug_raw = unicodedata.normalize("NFKD", clean_name)
        slug = "".join(ch for ch in slug_raw if not unicodedata.combining(ch)).lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
        if not slug:
            raise ValueError("El nombre de la etiqueta no contiene caracteres válidos.")

        prefix = "lang" if category == "language" else "mood"
        tag_id = f"{prefix}.{slug}"

        existing = self.get(tag_id)
        if existing:
            return existing

        new_tag = TagDefinition(
            id=tag_id,
            category=category,
            name=clean_name,
            display_name=clean_name,
            aliases=(clean_name.lower(), slug),
            custom=True,
        )

        custom_map = self._load_custom_tags()
        custom_map[tag_id] = new_tag
        path = self._custom_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "catalog_version": CATALOG_VERSION,
            "tags": [t.to_dict() for t in custom_map.values()],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return new_tag

    def export_catalog(self) -> dict[str, object]:
        tags = list(self.all_tags().values())
        return {
            "catalog_version": CATALOG_VERSION,
            "languages": [t.to_dict() for t in tags if t.category == "language"],
            "moods": [t.to_dict() for t in tags if t.category == "mood"],
        }


tag_catalog = TagCatalog()
