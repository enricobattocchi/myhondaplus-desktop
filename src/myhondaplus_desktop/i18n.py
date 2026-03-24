"""Simple JSON-based internationalization."""

import json
import locale
import logging
from importlib.resources import files

logger = logging.getLogger(__name__)

_TRANSLATIONS_PKG = files("myhondaplus_desktop") / "translations"

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}
_active_lang: str = "en"


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
        try:
            sys_locale = locale.getdefaultlocale()[0] or ""
            lang = sys_locale.split("_")[0]  # e.g. "it_IT" -> "it"
        except Exception:
            lang = "en"

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
