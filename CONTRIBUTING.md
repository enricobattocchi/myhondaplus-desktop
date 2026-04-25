# Contributing

Thanks for your interest in contributing to the unofficial My Honda+ desktop app!

## Reporting issues

If something isn't working, please [open an issue](https://github.com/enricobattocchi/myhondaplus-desktop/issues) with:

- Your OS and Python version
- Your vehicle model
- A description of what you expected to see and what you actually saw (redact any personal data)

## Development setup

```bash
git clone https://github.com/enricobattocchi/myhondaplus-desktop.git
cd myhondaplus-desktop
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

To run the app locally:

```bash
python -m myhondaplus_desktop
```

To run against a local in-development copy of `pymyhondaplus`:

```bash
.venv/bin/pip install -e /path/to/pymyhondaplus --no-deps
```

## Running tests and linting

```bash
python -m pytest
ruff check src/ tests/
```

Both must pass before a PR can be merged.

## Submitting changes

1. Fork the repo and create a branch from `main`.
2. Make your changes. Add tests for new functionality.
3. Run `pytest` and `ruff check` locally.
4. Open a pull request with a clear description of what you changed and why.

## Architecture

```
src/myhondaplus_desktop/
  app.py                    — MainWindow, MainScreen (view layer), entry point
  main_screen_controller.py — coordinates workers, state, view updates
  session.py                — owns Settings + HondaAPI + credential storage
  workers.py                — QThread subclasses for API calls
  config.py                 — paths (platformdirs) + Settings dataclass
  i18n.py                   — JSON-based translation loader, t() helper, t_lib() bridge to pymyhondaplus
  icons.py                  — Lucide SVG icon loader
  widgets/
    dashboard.py            — EV status card grid
    trips.py                — trip history table + stats + CSV export
    geofence.py             — native tile map (QGraphicsView + OSM) + save/clear controls
    vehicle.py              — vehicle info, subscription, Capabilities + Services modals
    schedules.py            — climate/charge schedule dialogs
    login.py                — login form + device registration flow
    status_bar.py           — bottom status/error bar
  translations/*.json       — 13 locales (en is canonical)
  icons/*.svg               — Lucide icon set
scripts/
  build_pyinstaller.py      — PyInstaller bundling
  check_release_version.py  — CI gate: tag must match __version__
  smoke_test_bundle.py      — post-build sanity check
tests/                      — pytest, ~109 tests
```

**Pattern:** view (MainScreen/widgets) exposes public methods → controller calls workers + connects signals + updates view → workers emit `finished` / `error`. Views never import workers directly (except `login.py` and `trips.py`).

### Library coupling

The app depends on `pymyhondaplus` for:

- `HondaAPI` — all API communication
- `get_translator(locale)` — used by `i18n.t_lib(key)` to resolve library-owned strings (capability state labels, geofence states, geofence error texts) without duplicating translations in the desktop's JSONs
- `VehicleCapabilities.active_api_keys()` / `not_supported_api_keys()` — read directly by the Capabilities modal

When adding a new feature that requires a library change, bump `pymyhondaplus` in `pyproject.toml` and `README.md` (both pin to the same version).

| Concern | Lives in |
|---|---|
| Capability raw API key labels | Library |
| Geofence state labels (Active / Activating / etc.) | Library (`geofence_state_*` keys via `t_lib()`) |
| Geofence error messages | Library (`geofence_*_error` keys via `t_lib()`) |
| Dashboard tile labels, dialog titles, button text | Desktop JSONs |
| Subscription service descriptions | Honda's API response (no translation layer) |

### Working with the codebase

- The `EVStatus` object from `pymyhondaplus` has dict-style access (`.get()`, `[]`, `in`). Treat it as a dict in widget code.
- Capabilities expose attribute access via `__getattr__`: `caps.remote_lock` works for known names. Unknown names raise `AttributeError`. Use `caps.active_api_keys()` to enumerate.
- No abstractions beyond what already exists. Zero base classes for widgets, zero registries.
- Helpers are module-level (`_card`, `_row`, `_selectable`).
- Translation keys use dot notation (`"dashboard.battery"`). Look at `en.json` before inventing new keys.

### Geofence widget

The geofence widget uses a native `QGraphicsView` tile map (OSM tiles). Map changes require running the app, not just running pytest.

## Translations

Translation files live in `src/myhondaplus_desktop/translations/`. Each language is a single JSON file named with its [ISO 639-1](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) code (e.g. `de.json` for German). The reference file is `en.json`.

### Via GitHub Issue (easiest)

1. Open an issue using the **Translation** template.
2. Pick your language and contribution type.
3. **New translation** — copy [`en.json`](src/myhondaplus_desktop/translations/en.json), translate the values, and paste the full JSON into the "Full translated JSON" field.
4. **Correction** — list only the keys that need fixing in the "Corrections" field (dotted key path + corrected value).
5. A maintainer will open the PR on your behalf.

### Via Pull Request

#### New language

1. Copy `src/myhondaplus_desktop/translations/en.json` to `src/myhondaplus_desktop/translations/<lang>.json`.
2. Translate all the **values** (right side). Keep the **keys** (left side) unchanged.
3. Keep `{placeholders}` in curly braces exactly as they are — they get replaced at runtime.
4. Validate your JSON.
5. Open a pull request.

#### Correction

1. Edit the existing `src/myhondaplus_desktop/translations/<lang>.json` file directly.
2. Open a pull request describing what you changed and why.

### Tips

- If you're unsure about a translation, leave it as the English value — the app falls back to English for any missing key.
- You don't need to translate every key. Partial translations work fine.
- The new language will appear automatically in the app's language selector.

## Code style

- Python ≥3.11. Uses `match`, `X | Y` union types, etc.
- PyQt6 — not PyQt5. Signals are `pyqtSignal`.
- Tags use bare version numbers (`2.7.0`), not `v2.7.0`. The version lives in `src/myhondaplus_desktop/__init__.py` (`__version__`); `pyproject.toml` reads it via `dynamic = ["version"]`.
- 13 translation files must stay in sync. `en.json` is the source of truth.

## Release process

1. Bump `__version__` in `src/myhondaplus_desktop/__init__.py`.
2. Bump the `pymyhondaplus` pin in `pyproject.toml` and `README.md` if a new library version is required.
3. Verify `pytest` and `ruff check` pass.
4. PR → merge to `main` (merge commit).
5. Tag `X.Y.Z` on the merge commit. Push the tag.
6. `gh release create X.Y.Z` — the GitHub release IS the release (HACS-style distribution; no PyPI workflow).
