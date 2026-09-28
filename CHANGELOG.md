# Changelog

All notable changes to this repository are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/).

## Unreleased

- Fixed `podcast`'s and `review-scout`'s `ledger.py` iterating state files
  in raw `glob()` order, which is filesystem-dependent. `dedup` pair
  orientation (and the order of every cross-show/cross-app listing)
  differed between macOS and Linux, so the `test` job failed on Linux CI.
  State files are now read in sorted order, with a regression test per
  plugin that forces both orders.
- Fixed `review-scout`'s `dedup` skipping any pair whose batch labels
  matched, even across different apps, so App A `v2.0` and App B `v2.0`
  were never compared. It now skips only pairs from the same app and the
  same batch.
- Removed `evals/signal-scout/` and its `evals` CI job (both added earlier
  in this release cycle). The fixtures were copied from litmus's
  `examples/signal-scout`, which describes the separate prospect-finding
  signal-scout repo (individuals, segments, openers). The `signal-scout`
  plugin here is a report renderer and never produces that output, and its
  `SKILL.md` is not the same file as the upstream one. The fixture outputs
  were hand-written and graded against a baseline without running any
  skill, so the job could not catch a regression here. The renderer's
  deterministic behavior is covered by `tests/test_render_report.py` in the
  `test` job.
- Added a `tests/` suite (stdlib `unittest`, no new dependency) covering
  `podcast`'s `ledger.py`/`resolve.py`, `review-scout`'s
  `ledger.py`/`resolve.py`, and `signal-scout`'s `render_report.py`:
  cross-show/cross-batch dedup scoring, prediction scoreboard and
  stale-sweep math, RSS/VTT and App Store review parsing, and payload
  validation/rendering. `ideation`, `research-suite`, and `signal-outreach`
  have no tests yet.
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
