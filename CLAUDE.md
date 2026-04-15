# CLAUDE.md — myhondaplus-desktop

## What this is

Desktop GUI (PyQt6) for Honda Connect Europe ("My Honda+"). Talks to Honda's API
via the `pymyhondaplus` library. Single-window app: login screen, then tabbed main
screen (Dashboard, Trips, Geofence, Vehicle). Background API calls run in QThread
workers; the GUI thread never blocks.

## Architecture at a glance

```
src/myhondaplus_desktop/
  app.py              – MainWindow, MainScreen (view layer), entry point
  main_screen_controller.py – coordinates workers, state, and view updates
  session.py           – owns Settings + HondaAPI + credential storage
  workers.py           – QThread subclasses for every API call
  config.py            – paths (platformdirs) + Settings dataclass
  i18n.py              – JSON-based translation loader, t() helper
  icons.py             – Lucide SVG icon loader, theme-aware color replacement
  widgets/
    dashboard.py       – EV status card grid
    trips.py           – trip history table + stats + CSV export
    geofence.py        – native tile map (QGraphicsView + OSM) + save/clear controls
    vehicle.py         – static vehicle info + subscription details
    schedules.py       – climate/charge schedule dialogs
    login.py           – login form + device registration flow
    status_bar.py      – bottom status/error bar
  translations/*.json  – 13 locales (en is canonical)
  icons/*.svg          – Lucide icon set
scripts/
  build_pyinstaller.py – PyInstaller bundling
  check_release_version.py – CI gate: tag must match __version__
  smoke_test_bundle.py – post-build sanity check for PyInstaller output
tests/                 – pytest, ~1900 lines, no fixtures beyond stdlib
```

**Key pattern:** View (MainScreen/widgets) exposes public methods. Controller
calls workers, connects signals, updates view. Workers emit `finished`/`error`
signals with results. Views never import workers directly (except login.py and
trips.py which manage their own workers for self-contained flows).

## Working with this codebase

### Think before coding

- Read the file you're about to change. Understand what the current code does
  before proposing modifications.
- The EVStatus object from `pymyhondaplus` is a dataclass with dict-style access
  (`.get()`, `[]`, `in`). Treat it as a dict in widget code — don't add
  isinstance checks or type coercions.
- `pymyhondaplus` is an external dependency that changes independently. When
  something looks wrong in API data, check the library version and its actual
  return types before "fixing" the desktop code.

### Simplicity first

- No abstractions beyond what exists. The codebase has zero base classes for
  widgets, zero registries, zero event buses. Keep it that way.
- Helper functions are module-level (`_card`, `_row`, `_selectable`) not methods
  on a base class. Follow this pattern.
- Settings is a flat dataclass with two fields. Don't add layers.
- Translation keys use dot notation (`"dashboard.battery"`). Look at `en.json`
  before inventing new keys.

### Surgical changes

- Touch only what the task requires. Don't reformat, don't add docstrings to
  unchanged code, don't reorganize imports you didn't modify.
- The `icons/` directory contains specific Lucide SVGs. Before using an icon name
  in code, verify the `.svg` file exists.
- Version lives in `__init__.py` (`__version__`), pulled dynamically by
  `pyproject.toml`. Change it in exactly one place.
- For releases, use the `/release` skill.

### Goal-driven execution

- Run `python -m pytest` (from repo root) to validate changes. Fix what breaks.
- Lint with `ruff check src/ tests/`. The project selects `E,F,W,I,UP,B` rules,
  ignores `E501`. Don't add lint config.
- No test framework beyond pytest. No mocking library beyond `unittest.mock`.
  Tests monkeypatch or use `MagicMock` — follow existing patterns.
- The geofence widget uses a native QGraphicsView tile map (OSM tiles).
  Changes to the map require testing in a running app, not just pytest.

## Commands

```bash
# Run tests
python -m pytest

# Lint
ruff check src/ tests/

# Run the app
python -m myhondaplus_desktop
```

## Things to know

- Python >=3.11 required. Uses `match`, `X | Y` union types, etc.
- PyQt6 — not PyQt5. Signal/slot syntax is `pyqtSignal`, not the old-style strings.
- 13 translation files must stay in sync. `en.json` is the source of truth.
  `TRANSLATING.md` documents the process.
- Tags and releases use bare version numbers (`2.6.0`), not `v2.6.0`.
- `pymyhondaplus` coordinates are pre-normalized floats (since 5.7.1b1). No DMS
  conversion needed in this codebase.
