# AGENTS.md

Fast orientation for AI agents working on this repo. Humans should start with [`CONTRIBUTING.md`](CONTRIBUTING.md), which documents the architecture, conventions, test layout, and release process in full. This file complements that with quick-navigation pointers for agents starting cold; defer to CONTRIBUTING.md when in doubt.

Sections 2, 3, and 5 mirror the canonical text in [`pymyhondaplus/AGENTS.md`](https://github.com/enricobattocchi/pymyhondaplus/blob/main/AGENTS.md) — update there first, then propagate.

## 1. What this repo is

The unofficial PyQt6 desktop app for My Honda+ / Honda Connect Europe vehicles, distributed as PyInstaller bundles for Linux, macOS, and Windows. It consumes the [`pymyhondaplus`](https://github.com/enricobattocchi/pymyhondaplus) library for all upstream API work and presents vehicle status, trips, geofence, and remote controls in a native GUI.

## 2. Naming

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

Refer to the upstream service as "the My Honda+ API" or "the Honda Connect Europe API" in code, comments, commit messages, PR descriptions, log strings, and test names — matching the framing used in the public READMEs. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full style guide.

## 3. The three-repo ecosystem

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

[`pymyhondaplus`](https://github.com/enricobattocchi/pymyhondaplus) (Python library + CLI) is consumed by:

- [`myhondaplus-homeassistant`](https://github.com/enricobattocchi/myhondaplus-homeassistant) — Home Assistant integration, pinned `==X.Y.Z` (HA convention).
- [`myhondaplus-desktop`](https://github.com/enricobattocchi/myhondaplus-desktop) — PyQt6 desktop app, pinned `>=X.Y.Z`.

**Ownership boundaries** — each concern lives in exactly one repo:

- **Library owns**: API request/response shapes, auth flow, `EVStatus` parsing, enum normalization (`charge_status`, `home_away`, `climate_temp`, geofence states), `VehicleCapabilities` resolution, capability raw-API-key labels, geofence state labels, geofence error messages, library-side translations (CLI strings + the `t_lib()` keys consumers bridge to).
- **HA integration owns**: entity descriptors, coordinators, config flow, services, `strings.json` + `translations/*.json`, error-handling conventions for HA.
- **Desktop owns**: view layer (MainWindow / widgets), controller, workers, dashboard / trip / geofence / vehicle UI, desktop `translations/*.json`, PyInstaller bundling.

If a task feels like it crosses boundaries, default to "the library owns the API/parsing/canonical enums; consumers are presentation" and confirm with the maintainer before editing across repos.

**Triage rule.** When investigating an issue or fix in a consumer repo (HA or desktop), use the ownership boundaries above. If the symptom is in library-owned territory (API request/response shape, parsing, enum normalization, capability resolution, library-owned translation strings), the issue or PR should be opened in `pymyhondaplus` — even if it was first surfaced through a consumer. When in doubt, a short Python repro against the library is the fastest way to confirm.

## 4. Where to touch code

| Task | Files |
|---|---|
| New dashboard tile | `src/myhondaplus_desktop/widgets/dashboard.py`; translation key in `src/myhondaplus_desktop/translations/en.json` (then propagate to the other 12 locales); access `EVStatus` as a dict (`.get()`, `[]`, `in`) |
| New modal / dialog | new widget under `src/myhondaplus_desktop/widgets/`; wire it in `main_screen_controller.py`; translation keys; tests in `tests/` |
| New worker for an API call | `src/myhondaplus_desktop/workers.py` (`QThread` subclass with `finished` / `error` signals); the controller connects them; UI mutation can be optimistic |
| New translated string | `src/myhondaplus_desktop/translations/en.json` (canonical) + 12 other locales; `tests/test_i18n.py` enforces coverage. **Library-owned strings** (geofence states, capability labels, geofence errors) come via `i18n.t_lib(key)` — do not duplicate them in desktop JSONs. |
| Bump library dep | `pyproject.toml` (`pymyhondaplus>=X.Y.Z`) and `README.md` must mirror the same pin; `scripts/check_release_version.py` enforces tag = `__version__` |
| Capabilities modal change | `src/myhondaplus_desktop/widgets/vehicle.py`; relies on the library's `caps.active_api_keys()` / `not_supported_api_keys()` |
| Geofence widget change | `src/myhondaplus_desktop/widgets/geofence.py`; **requires running the app**, not just `pytest` — the tile map is a `QGraphicsView` rendering surface |
| New language | copy `translations/en.json` → `translations/<lang>.json`, translate the values only, keep keys + `{placeholders}` unchanged; the language appears automatically in the selector |

## 5. Cross-repo workflows

*Mirrored from `pymyhondaplus/AGENTS.md` — update there first.*

- **Release order is library first, then consumers.** Bump `pymyhondaplus`, tag, GitHub-release; then update HA `manifest.json` `requirements` (`==X.Y.Z`) and/or desktop `pyproject.toml` + `README.md` (`>=X.Y.Z`), then release each consumer.
- **Pin update rule**: HA pins exact (Home Assistant convention); desktop pins minimum.
- **Translation-drift PRs** may span library + HA. When a string converges in wording, move the pair from `_KNOWN_DRIFT` to `ENFORCED_OVERLAPS` in the same PR (HA test: `tests/test_translation_drift.py`).
- **Cross-repo change checklist**: land library-owned API/parsing/auth/translation behavior in `pymyhondaplus` first; update HA's exact pin and desktop's minimum pin only after a library release; keep consumer enum options, entity descriptors, and UI copy aligned with canonical library behavior.

## 6. Common pitfalls

- `EVStatus` looks like a dataclass but treat it as a dict (`get` / `[]` / `in`). Widgets that try `getattr` on it will surprise themselves.
- Capability access is via `__getattr__`; unknown names raise `AttributeError`. Use `caps.active_api_keys()` to enumerate.
- Do not introduce abstractions or registries. The pattern is module-level helpers (`_card`, `_row`); follow it.
- Translation keys use dot notation (`"dashboard.battery"`). Look at `en.json` before inventing new keys.
- PyQt6, not PyQt5 — signals are `pyqtSignal`.
- Library-owned strings (geofence states, capability labels, geofence errors) must come through `t_lib()`, not be re-typed into desktop JSONs.

## 7. Gates and local commands

- Setup: `pip install -e ".[dev]"`
- Use a sibling library checkout while testing integration changes: `.venv/bin/pip install -e /path/to/pymyhondaplus --no-deps`
- Tests: `python -m pytest`
- Lint: `ruff check src/ tests/`
- Release version check: `python scripts/check_release_version.py X.Y.Z`

`Test` (pytest on Python 3.11/3.12/3.13 matrix), `Lint` (ruff). Tag is the bare version (e.g. `2.7.0`, not `v2.7.0`); `__version__` in `src/myhondaplus_desktop/__init__.py` must match the tag (`scripts/check_release_version.py` enforces this). PyInstaller bundle workflows (`build-linux.yml`, `build-macos.yml`, `build-windows.yml`) run on release publish.

## 8. Full reference

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full folder tree, view/controller/worker pattern, library-coupling concern table, geofence widget notes, code style, and release process. The same guidance that applies to human contributors applies to agents.
