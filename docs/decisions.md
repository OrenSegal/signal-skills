# Decisions

Three decisions behind the repo's shape. Where the reasoning was not written down at the time, this says "not recorded".

## 1. Copy the shared renderer into each plugin, and check the copies in CI

**Context.** `podcast`, `review-scout` and `ideation` all render with `signal-report`'s `render_report.py` and `template.html`. `/plugin install <name>@oren-signal-skills` fetches only that plugin's directory.

**Decision.** Each consumer ships a generated copy. `scripts/sync-shared-files.sh` regenerates them from `plugins/signal-report`, and CI runs it with `--check` so a hand-edited copy fails.

**Alternatives considered.** A symlink or a cross-plugin import: rejected because it resolves to nothing after a single-plugin install (the script header says this broke once; the breaking commit is not recorded). A shared pip package: rejected to keep the plugins stdlib only (CONTRIBUTING.md).

**Consequences.** There are 6 copies in total (2 files × 3 consumers), and each edit to a source file regenerates its 3 copies. Contributors must remember to run the script; CI catches it if they don't.

**Evidence.** 46d4834 (script), `.github/workflows/check-shared-files.yml` (`drift` job).

## 2. No eval suite that grades hand-written outputs

**Context.** b284062 added a litmus suite copied from another repo. Its fixtures described the separate signal-scout prospect finder, and CI graded hand-written outputs against a baseline without running any skill.

**Decision.** Removed it (#1). Only deterministic code is tested: ledgers, resolvers, the report renderer and the outreach generator, 79 unittest cases.

**Alternatives considered.** Keeping the suite with a relabelled name, as signal-scout did: not chosen here because the fixtures graded a different skill. Recording real LLM runs: not done; it costs API usage and varies between runs.

**Consequences.** The LLM steps (what `podcast` extracts, what `ideation` proposes) have no automated check.

**Evidence.** c3a0f28 / #1.

## 3. `review-scout` uses only sources with a documented, permitted access path

**Context.** Review mining could scrape store pages.

**Decision.** iOS reviews come from Apple's public RSS feed; Android reviews come from Google's Play Developer API, which only works for an app you own. Where no permitted path exists, the skill says so.

**Alternatives considered.** Scraping store pages or third-party review APIs. Reasoning not recorded beyond the SKILL.md rule.

**Consequences.** Android coverage is limited to your own apps, and needs a service account.

**Evidence.** `plugins/review-scout/SKILL.md`, `tests/test_review_scout_resolve.py`.
