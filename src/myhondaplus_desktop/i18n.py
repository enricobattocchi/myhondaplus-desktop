"""Simple JSON-based internationalization."""

import json
import locale
import logging
from importlib.resources import files

from pymyhondaplus import CAPABILITY_API_KEY_TO_TRANSLATION_KEY
from pymyhondaplus import get_translator as _lib_get_translator

logger = logging.getLogger(__name__)

_TRANSLATIONS_PKG = files("myhondaplus_desktop") / "translations"

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
_active_lang: str = "en"


def _detect_language() -> str:
    """Auto-detect a language code from the current locale."""
    try:
        sys_locale = locale.getlocale()[0] or ""
    except Exception:
        return "en"
    return sys_locale.split("_")[0] if sys_locale else "en"


def available_languages() -> list[str]:
    """Return list of available language codes (e.g. ['en', 'it'])."""
    langs = []
    for f in _TRANSLATIONS_PKG.iterdir():
        if str(f).endswith(".json"):
            langs.append(str(f).rsplit("/", 1)[-1].removesuffix(".json"))
    return sorted(langs)


def _load_json(lang: str) -> dict[str, str]:
    """Load a translation file, return empty dict if not found."""
    path = _TRANSLATIONS_PKG / f"{lang}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load translation '%s': %s", lang, e)
        return {}


def active_language() -> str:
    """Return the currently active language code."""
    return _active_lang


def load_language(lang: str = ""):
    """Load a language. Empty string = auto-detect from system locale."""
    global _strings, _fallback, _active_lang

    _fallback = _load_json("en")

    if not lang:
        lang = _detect_language()

    if lang and lang != "en":
        _strings = _load_json(lang)
    else:
        _strings = _fallback

    _active_lang = lang
    logger.info("Language: %s (%d strings, %d fallback)",
                lang, len(_strings), len(_fallback))


def t(key: str, **kwargs) -> str:
    """Translate a key, with optional {placeholder} substitution."""
    text = _strings.get(key, _fallback.get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def active_capability_labels(caps) -> list[str]:
    """Return localized labels for a vehicle's active capabilities.

    Iterates VehicleCapabilities.raw, filters to active capabilities, sorts
    alphabetically by the raw Honda API key, and returns translated labels
    from the library's translations where available. Capabilities this
    library version doesn't yet know about render as the raw API key, so
    new Honda additions are never silently hidden.
    """
    lib_t = _lib_get_translator(_active_lang)
    raw = getattr(caps, "raw", {}) or {}
    labels = []
    for api_key in sorted(raw):
        entry = raw[api_key]
        if not isinstance(entry, dict) or entry.get("featureStatus") != "active":
            continue
        tkey = CAPABILITY_API_KEY_TO_TRANSLATION_KEY.get(api_key)
        labels.append(lib_t(tkey) if tkey else api_key)
    return labels
