# Contributing Translations

Translations are simple JSON files — one per language.

## How to add a new language

1. Copy `src/myhondaplus_desktop/translations/en.json` to a new file named with the [ISO 639-1 language code](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes) (e.g. `de.json` for German, `fr.json` for French)

2. Translate all the **values** (right side). Keep the **keys** (left side) unchanged.

3. Keep `{placeholders}` in curly braces exactly as they are — they get replaced with dynamic values at runtime. For example:
   ```json
   "app.version": "Version {version}"
   ```
   In German this might be:
   ```json
   "app.version": "Version {version}"
   ```

4. Submit a pull request. The new language will appear automatically in the app's About dialog.

## File structure

```
src/myhondaplus_desktop/translations/
  en.json   ← English (reference)
  it.json   ← Italian
  de.json   ← your new language here
```

## Tips

- If you're unsure about a translation, leave it as the English value — the app falls back to English for any missing key
- You don't need to translate every single key. Partial translations work fine
- Test your translation by setting the language in the app's About dialog and restarting
