# Contributing

Thanks for your interest in contributing to the unofficial My Honda+ desktop app!

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

1. Copy `src/myhondaplus_desktop/translations/en.json` to `src/myhondaplus_desktop/translations/<lang>.json` (e.g. `pt.json` for Portuguese).
2. Translate all the **values** (right side). Keep the **keys** (left side) unchanged.
3. Keep `{placeholders}` in curly braces exactly as they are — they get replaced at runtime.
4. Validate your JSON (a trailing comma or missing quote will break the file).
5. Open a pull request.

#### Correction

1. Edit the existing `src/myhondaplus_desktop/translations/<lang>.json` file directly.
2. Open a pull request describing what you changed and why.

### Tips

- If you're unsure about a translation, leave it as the English value — the app falls back to English for any missing key.
- You don't need to translate every single key. Partial translations work fine.
- The new language will appear automatically in the app's language selector.
