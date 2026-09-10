# Changelog

All notable changes to this repository are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

- Added `evals/signal-scout/` — skill-behavior evals for the bundled
  `signal-scout` plugin, gated in CI via `litmus gate` against a checked-in
  baseline. Same suite as upstream signal-scout's own evals, since the
  bundled `SKILL.md` is byte-identical; catches behavior regressions in the
  distributed copy, not just the source repo.
- Added a `tests/` suite (stdlib `unittest`, no new dependency) covering
  each plugin's core logic: cross-show/cross-batch dedup scoring, prediction
  scoreboard and stale-sweep math, RSS/VTT and App Store review parsing, and
  `render_report.py` payload validation/rendering.
- Added a `test` job to CI that runs the suite on every push and pull
  request, alongside the existing shared-file drift check.
- Added `CONTRIBUTING.md` (setup, how to run tests, the shared-file sync
  workflow) and this changelog.

## 2026-09-08

- Shipped `review-scout`, `ideation`, and `research-suite` as new plugins
  alongside `podcast` and `signal-scout`.
- Added `signal-outreach`, a companion skill that turns a `signal-scout`
  prospect report into per-prospect next actions (outreach sequences,
  content/GTM briefs, BD pitches).
- Added `scripts/sync-shared-files.sh`, the generator/checker for
  `signal-scout`'s `render_report.py`/`template.html` being copied (not
  symlinked) into `podcast`, `ideation`, and `review-scout` so each plugin
  installs standalone.
- Added the `check-shared-files` CI workflow and a `FUNDING` config.
- Added `.env` to `.gitignore`.

## 2026-07-21

- Added YouTube support to the `podcast` skill (resolve a channel/video URL,
  pull auto-caption transcripts via `yt-dlp`).

## 2026-07-16

- Renamed to `podcast-skill`; added Codex CLI support alongside Claude Code.
- Packaged `podcast` and `signal-scout` as installable Claude Code plugins.
