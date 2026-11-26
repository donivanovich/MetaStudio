"""Smart language and mood tag inference engine using original MP3 tags & music sources."""

import re
from pathlib import Path

from backend.models.domain import SessionState, TagSuggestion, TrackState
from backend.services.audio.id3_service import read_original_id3_metadata
from backend.services.classification.catalog import tag_catalog

MIN_CONFIDENCE = 0.55

# Ordered from most specific compound genres to broad genres (Rule 11.3 orientative heuristics)
GENRE_TO_MOOD_RULES: list[tuple[str, list[tuple[str, float]]]] = [
    ("sad trap", [("mood.sad", 0.88), ("mood.melancholic", 0.80)]),
    ("emo rap", [("mood.sad", 0.85), ("mood.melancholic", 0.78)]),
    ("lo-fi", [("mood.chill", 0.86), ("mood.relaxed", 0.82)]),
    ("lofi", [("mood.chill", 0.86), ("mood.relaxed", 0.82)]),
    ("chillhop", [("mood.chill", 0.85), ("mood.relaxed", 0.78)]),
    ("reggaeton", [("mood.hype", 0.78), ("mood.energetic", 0.64)]),
    ("urbano latino", [("mood.hype", 0.74), ("mood.chill", 0.58)]),
    ("latin urban", [("mood.hype", 0.74), ("mood.chill", 0.58)]),
    ("dembow", [("mood.hype", 0.82), ("mood.energetic", 0.74)]),
    ("drill", [("mood.dark", 0.82), ("mood.aggressive", 0.74)]),
    ("trap", [("mood.hype", 0.74), ("mood.dark", 0.68)]),
    ("r&b", [("mood.chill", 0.78), ("mood.romantic", 0.72)]),
    ("rnb", [("mood.chill", 0.78), ("mood.romantic", 0.72)]),
    ("neo-soul", [("mood.chill", 0.78), ("mood.romantic", 0.70)]),
    ("soul", [("mood.romantic", 0.72), ("mood.melancholic", 0.62)]),
    ("bolero", [("mood.romantic", 0.84), ("mood.nostalgic", 0.74)]),
    ("bachata", [("mood.romantic", 0.82), ("mood.chill", 0.62)]),
    ("ballad", [("mood.romantic", 0.74), ("mood.melancholic", 0.70)]),
    ("balada", [("mood.romantic", 0.76), ("mood.melancholic", 0.72)]),
    ("synthwave", [("mood.nostalgic", 0.84), ("mood.chill", 0.64)]),
    ("vaporwave", [("mood.nostalgic", 0.80), ("mood.chill", 0.74)]),
    ("heavy metal", [("mood.aggressive", 0.86), ("mood.energetic", 0.78)]),
    ("death metal", [("mood.aggressive", 0.90), ("mood.dark", 0.82)]),
    ("metal", [("mood.aggressive", 0.80), ("mood.energetic", 0.76)]),
    ("punk", [("mood.energetic", 0.82), ("mood.aggressive", 0.76)]),
    ("hard rock", [("mood.energetic", 0.80), ("mood.aggressive", 0.68)]),
    ("rock en español", [("mood.energetic", 0.70), ("mood.nostalgic", 0.62)]),
    ("indie rock", [("mood.nostalgic", 0.68), ("mood.melancholic", 0.62)]),
    ("rock", [("mood.energetic", 0.74), ("mood.aggressive", 0.58)]),
    ("dance pop", [("mood.happy", 0.78), ("mood.energetic", 0.76)]),
    ("electropop", [("mood.energetic", 0.76), ("mood.happy", 0.68)]),
    ("pop", [("mood.happy", 0.70), ("mood.energetic", 0.66)]),
    ("classical", [("mood.relaxed", 0.76), ("mood.melancholic", 0.68)]),
    ("ambient", [("mood.relaxed", 0.86), ("mood.chill", 0.76)]),
    ("jazz", [("mood.chill", 0.76), ("mood.relaxed", 0.72)]),
    ("bossa nova", [("mood.relaxed", 0.84), ("mood.chill", 0.78)]),
    ("house", [("mood.hype", 0.76), ("mood.energetic", 0.74)]),
    ("techno", [("mood.dark", 0.74), ("mood.energetic", 0.76)]),
    ("edm", [("mood.hype", 0.80), ("mood.energetic", 0.78)]),
    ("hip-hop", [("mood.hype", 0.68), ("mood.energetic", 0.60)]),
    ("hip hop", [("mood.hype", 0.68), ("mood.energetic", 0.60)]),
    ("acoustic", [("mood.relaxed", 0.74), ("mood.chill", 0.68)]),
    ("folk", [("mood.nostalgic", 0.72), ("mood.melancholic", 0.64)]),
    ("blues", [("mood.melancholic", 0.80), ("mood.sad", 0.70)]),
    ("goth", [("mood.dark", 0.86), ("mood.melancholic", 0.76)]),
    ("darkwave", [("mood.dark", 0.86), ("mood.melancholic", 0.74)]),
]

GENRE_TO_LANGUAGE_HINTS: list[tuple[str, str, float]] = [
    ("reggaeton", "lang.es", 0.78),
    ("urbano latino", "lang.es", 0.78),
    ("rock en español", "lang.es", 0.85),
    ("pop latino", "lang.es", 0.78),
    ("flamenco", "lang.es", 0.82),
    ("corridos", "lang.es", 0.85),
    ("bachata", "lang.es", 0.80),
    ("salsa", "lang.es", 0.76),
    ("balada", "lang.es", 0.78),
    ("k-pop", "lang.ko", 0.88),
    ("korean", "lang.ko", 0.88),
    ("j-pop", "lang.ja", 0.88),
    ("j-rock", "lang.ja", 0.86),
    ("anime", "lang.ja", 0.72),
    ("chanson", "lang.fr", 0.85),
    ("french pop", "lang.fr", 0.85),
    ("mpb", "lang.pt", 0.84),
    ("bossa nova", "lang.pt", 0.80),
    ("sertanejo", "lang.pt", 0.86),
    ("funk brasileiro", "lang.pt", 0.86),
    ("italo", "lang.it", 0.78),
    ("cantautori", "lang.it", 0.84),
    ("schlager", "lang.de", 0.85),
    ("krautrock", "lang.de", 0.78),
    ("classical", "lang.instrumental", 0.68),
    ("instrumental", "lang.instrumental", 0.88),
]

_HANGUL_RE = re.compile(r"[\uac00-\ud7af]")
_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_SPANISH_DIACRITICS_RE = re.compile(r"[ñ¿¡]", flags=re.IGNORECASE)


def classify_track(
    *,
    title: str,
    artists: list[str],
    original_genres: list[str],
    original_language: str | None = None,
    mp3_path: Path | None = None,
) -> list[TagSuggestion]:
    """
    Infer Language and Mood tag suggestions with provenance and confidence scores.
    Conservative by design: never invents tags when confidence is below MIN_CONFIDENCE.
    """
    genres = [g.strip() for g in original_genres if g and g.strip()]
    languages: list[str] = [original_language.strip()] if original_language and original_language.strip() else []

    # 1. Inspect original MP3 TCON / TLAN when a local MP3 file is provided
    id3_genres: list[str] = []
    id3_languages: list[str] = []
    if mp3_path and mp3_path.is_file():
        orig = read_original_id3_metadata(mp3_path)
        id3_genres = orig.genres
        id3_languages = orig.languages
        genres = list(dict.fromkeys([*id3_genres, *genres]))
        languages = list(dict.fromkeys([*id3_languages, *languages]))

    suggestions: dict[str, TagSuggestion] = {}

    def _record(tag_id: str, confidence: float, source: str, rationale: str) -> None:
        if confidence < MIN_CONFIDENCE:
            return
        tag_def = tag_catalog.get(tag_id)
        if not tag_def:
            return
        prev = suggestions.get(tag_id)
        if prev is None or confidence > prev.confidence:
            suggestions[tag_id] = TagSuggestion(
                tag_id=tag_def.id,
                category=tag_def.category,
                name=tag_def.name,
                display_name=tag_def.display_name,
                confidence=round(min(confidence, 0.99), 2),
                source=source,
                rationale=rationale,
            )

    # --- Language Classification ---
    lang_found = False
    for raw_lang in languages:
        matched = tag_catalog.resolve_language_alias(raw_lang)
        if matched and matched.id != "lang.unknown":
            src = "mp3_tlan" if raw_lang in id3_languages else "metadata_language"
            _record(matched.id, 0.95, src, f"Idioma original detectado: {raw_lang}")
            lang_found = True
            break

    # Check instrumental markers in title or genre
    lower_title = (title or "").lower()
    if not lang_found and any(tok in lower_title for tok in ("(instrumental)", "[instrumental]", "instrumental version")):
        _record("lang.instrumental", 0.90, "title_indicator", "Indicador explícito de pista instrumental")
        lang_found = True

    # Genre-based regional language signal (does NOT confuse title language with song language)
    if not lang_found:
        for genre in genres:
            gl = genre.lower()
            for pattern, lang_id, conf in GENRE_TO_LANGUAGE_HINTS:
                if pattern in gl:
                    src = "mp3_tcon" if genre in id3_genres else "provider_genre"
                    _record(lang_id, conf, src, f"Idioma inferido por género musical ({genre})")
                    lang_found = True
                    break
            if lang_found:
                break

    # Script cues (Hangul / Kana / unique Spanish punctuation like ñ, ¿, ¡)
    if not lang_found:
        combined_text = f"{title} {' '.join(artists)}"
        if _HANGUL_RE.search(combined_text):
            _record("lang.ko", 0.82, "script_analysis", "Escritura Hangul detectada")
        elif _KANA_RE.search(combined_text):
            _record("lang.ja", 0.82, "script_analysis", "Escritura japonesa (Kana) detectada")
        elif _SPANISH_DIACRITICS_RE.search(title or ""):
            _record("lang.es", 0.72, "script_analysis", "Caracteres propios del español detectados")

    # --- Mood Classification (driven primarily by original MP3 TCON & provider genres) ---
    mood_scores: dict[str, tuple[float, str, str]] = {}

    for genre in genres:
        gl = genre.lower()
        src = "mp3_tcon" if genre in id3_genres else "provider_genre"

        # Direct mood keywords present in MusicBrainz/provider tags
        for mood_tag in tag_catalog.all_tags().values():
            if mood_tag.category != "mood":
                continue
            if gl == mood_tag.name.lower() or gl in mood_tag.aliases:
                prev = mood_scores.get(mood_tag.id)
                if not prev or 0.86 > prev[0]:
                    mood_scores[mood_tag.id] = (0.86, src, f"Etiqueta directa de fuente: {genre}")

        # Genre-to-mood heuristic mapping (most specific match wins per genre string)
        for pattern, mood_pairs in GENRE_TO_MOOD_RULES:
            if pattern in gl:
                for mood_id, conf in mood_pairs:
                    prev = mood_scores.get(mood_id)
                    if not prev or conf > prev[0]:
                        mood_scores[mood_id] = (
                            conf,
                            src,
                            f"Inferido a partir del género original '{genre}'",
                        )
                break  # Avoid double-matching broader rule (e.g. 'sad trap' shouldn't also fire 'trap')

    # Keep top 2 strongest mood suggestions (Rule 11.4: do NOT auto-assign all possible moods)
    top_moods = sorted(mood_scores.items(), key=lambda kv: kv[1][0], reverse=True)[:2]
    for mood_id, (conf, src, rationale) in top_moods:
        _record(mood_id, conf, src, rationale)

    # Order: language first, then moods by descending confidence
    ordered = sorted(
        suggestions.values(),
        key=lambda s: (0 if s.category == "language" else 1, -s.confidence),
    )
    return ordered


async def classify_track_enrichment_hook(
    _session: SessionState, track: TrackState
) -> None:
    """TrackProcessor hook: generates smart tag suggestions and initializes high-confidence defaults."""
    mp3_path = Path(track.downloaded_file_path) if track.downloaded_file_path else None
    suggestions = classify_track(
        title=track.title,
        artists=track.artists,
        original_genres=track.original_genres,
        original_language=track.original_language,
        mp3_path=mp3_path,
    )
    track.suggested_tags = suggestions

    # Pre-select high-confidence suggestions ONLY if the user hasn't already selected/persisted tags
    if not track.selected_tag_ids and suggestions:
        auto_selected: list[str] = []
        lang_picked = False
        mood_count = 0
        for s in suggestions:
            if s.category == "language" and not lang_picked and s.confidence >= 0.70:
                auto_selected.append(s.tag_id)
                lang_picked = True
            elif s.category == "mood" and mood_count < 2 and s.confidence >= 0.65:
                auto_selected.append(s.tag_id)
                mood_count += 1
        track.selected_tag_ids = auto_selected
