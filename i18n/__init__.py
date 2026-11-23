"""Tiny i18n helper: t(key, lang, **vars) with automatic English fallback."""
import json
import pathlib

LANGS = {"en": "English", "ta": "தமிழ்", "hi": "हिन्दी", "ml": "മലയാളം"}
_DIR = pathlib.Path(__file__).parent / "locales"
CACHE = {l: json.loads((_DIR / f"{l}.json").read_text(encoding="utf-8")) for l in LANGS}


def t(key, lang="en", **kw):
    s = CACHE.get(lang, {}).get(key) or CACHE["en"].get(key) or key
    try:
        return s.format(**kw)
    except (KeyError, IndexError, ValueError):
        return s
