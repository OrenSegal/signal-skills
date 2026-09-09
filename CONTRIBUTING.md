# Contributing

## Setup

No dependencies to install for the core logic — `ledger.py`, `resolve.py`,
and `render_report.py` in every plugin are stdlib-only Python 3. You only
need extras if you're touching a specific integration:

- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on `PATH` for the `podcast`
  skill's YouTube path (`brew install yt-dlp`).
- `google-api-python-client` + `google-auth` for `review-scout`'s Android
  (Play Store) path.

## Running the tests

```
python3 -m unittest discover -s tests -v
```

Tests live in `tests/` at the repo root and cover the core logic of each
plugin's `ledger.py`, `resolve.py`, and `render_report.py`: dedup scoring,
prediction scoreboard/stale-sweep math, RSS/VTT parsing, App Store review
parsing, and payload validation/rendering. `tests/_loader.py` loads each
plugin's same-named module (`ledger.py`, `resolve.py`) by file path under a
unique module name, since several plugins ship their own non-shared copy.

External network calls (iTunes/App Store fetches, yt-dlp subprocess calls)
are stubbed in tests; the parsing/scoring logic they feed is exercised for
real.

CI (`.github/workflows/check-shared-files.yml`) runs this suite on every
push and pull request, alongside the existing shared-file drift check.

## Editing the shared report renderer

`plugins/signal-scout/render_report.py` and `template.html` are the single
authored source; `podcast`, `review-scout`, and `ideation` each ship a
*generated* copy (not a symlink — see the comment at the top of
`scripts/sync-shared-files.sh` for why). After editing the `signal-scout`
source, run:

```
./scripts/sync-shared-files.sh
```

to regenerate the three consumer copies, then commit all of them together.
`./scripts/sync-shared-files.sh --check` (what CI runs) fails if a consumer
copy has drifted from the source.

## Pull requests

- Keep a plugin's `SKILL.md` in sync with any behavior change in its
  scripts — `SKILL.md` is the actual spec the skill runs on, not just docs.
- If you touch `ledger.py`, `resolve.py`, or `render_report.py` logic, add
  or update a test in `tests/` covering the change.
- Run the test suite and, if you touched `signal-scout`'s renderer, the
  sync script's `--check` mode, before opening a PR.
