---
name: release
description: Bump version, update docs, commit, tag, push, and create a GitHub release. Use when the user asks to release, ship, or publish a new version.
disable-model-invocation: true
argument-hint: <version>
---

Release version $ARGUMENTS of myhondaplus-desktop. Follow these steps exactly:

## 1. Determine version

If $ARGUMENTS is empty, figure out the next version:
- List commits since the last tag (`git log <last-tag>..HEAD --oneline`)
- New features = minor bump, bug fixes only = patch bump
- Ask the user to confirm before proceeding

## 2. Bump version

- Edit `src/myhondaplus_desktop/__init__.py`: set `__version__ = "<version>"`
- This is the ONLY place the version is defined

## 3. Update docs

- Check README.md for accuracy (no stale references, no duplicates)
- Check CLAUDE.md for stale descriptions
- Do NOT add content the user didn't ask for

## 4. Verify

- Run `python -m pytest` — all tests must pass
- Run `ruff check src/ tests/` — must be clean
- Run `grep -r QtWebEngine src/` or similar if a dependency was removed — verify no stale imports

## 5. Commit and push

- `git add` only the files you changed (never `git add -A`)
- Commit message: short summary of what's in this release
- `git tag <version>` (bare version, no `v` prefix)
- `git push origin main --tags`

## 6. Create GitHub release

```
gh release create <version> --title "<version>" --notes "$(cat <<'EOF'
## Changes

- bullet points summarizing what changed since last release
EOF
)"
```

Keep release notes concise. Group by: What's new, Fixes, Dependencies (only include sections that apply).

## Rules

- Tags use bare version numbers: `2.6.1` not `v2.6.1`
- Never skip tests or lint
- Never force push
- Flag binary size impact if dependencies changed
