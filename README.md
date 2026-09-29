# signal-skills

Six agent skills for Claude Code and Codex CLI that mine podcasts and user reviews for findings, turn those findings into build proposals, and render the results as a shareable report.

| Skill | What it does |
|-------|--------------|
| `podcast` | Mines a podcast (Apple Podcasts, Spotify, RSS, or YouTube) for ideas and predictions, and answers questions from everything mined so far. |
| `review-scout` | Mines app store, browser extension, or web/SaaS reviews into ranked bugs, feature-request clusters, and cross-version regressions. |
| `ideation` | Reads the findings from `podcast` and `review-scout` and proposes what to build, fix, or test next, with citations. |
| `signal-scout` | Renders a findings payload into one prioritized, shareable Artifact. |
| `research-suite` | A router that tells you which of the skills above fits your request. |
| `signal-outreach` | Turns a `signal-scout` prospect report into outreach sequences, content briefs, or BD pitches. |

Both tools read the same folder shape (`SKILL.md` plus scripts), just from different homes: `~/.claude/skills` for Claude Code and `~/.codex/skills` for Codex.

## The skills

**`podcast`** resolves a podcast URL to its feed or transcripts and mines episodes for ideas without dumping raw transcript into context. It tracks falsifiable predictions across episodes, dedups claims that show up on several shows, and answers questions straight out of the corpus you've built up.

**`review-scout`** applies the same extract-don't-summarize approach to user reviews. It only uses compliant, ToS-safe sources (Apple's public RSS feed and Google's official Play Developer API), and says so explicitly wherever no compliant path exists.

**`ideation`** goes one step past a finding: it turns findings into prioritized, cited proposals. A ledger keeps it from re-proposing the same idea on every run.

**`signal-scout`** is the shared reporting stage. It also works for any other source type that wants the same report shape.

**`research-suite`** maps the four mining, ideation, and reporting skills: which one fits which request, and how the shared pieces fit together. It is user-invoked only and never fires on its own.

**`signal-outreach`** picks the next action for each prospect type in a `signal-scout` prospect report: outreach sequences for Individuals, content/GTM briefs for Segments, BD pitches for Companies. It never sends anything automatically.

**Name clash:** this `signal-scout` only renders reports. It is unrelated to any other tool called "signal-scout" you may have installed from a different source (same author, different tool). If you have both, check which one loaded before invoking `/signal-scout`.

## Beyond a one-shot summary

Each mining run writes to a per-show or per-app ledger (`ledger.py`), so results build up across runs instead of resetting.

- **Query the whole corpus.** `ledger.py query --topic pricing` searches every finding `podcast` has recorded, across every show, without re-fetching transcripts.
- **Prediction scoreboard.** Falsifiable predictions made by guests are tracked and later resolved as confirmed, failed, or stale. `ledger.py scoreboard [--by-guest]` turns that into a hit-rate leaderboard showing which shows (or guests) turned out to be right over time.
- **Watch shows on a schedule.** `ledger.py subscribe --show <url>` combined with a `schedule`-skill cron job gives you a digest of new episodes without having to ask.
- **Web cross-checks.** Key claims and open predictions can be checked against independent sources on the open web (Claude Code's `WebSearch`). A confirmed prediction then carries a real citation, not just "a later episode agreed."
- **Regression detection.** `review-scout` flags a complaint whose wording overlaps with something already marked fixed in an earlier app version.
- **From findings to decisions.** `ideation` reads both mining skills' ledgers and proposes what to build, fix, or test next, citing the findings behind each proposal.
- **Token use.** Extraction is batched by transcript word count and runs on a cheap, fast model. Only synthesis, contradiction-spotting, and web-check judgment calls use the full session model. A deterministic script generates the report HTML, so the markup costs no tokens.

Each skill's `SKILL.md` is the spec the skill actually runs on and has the full details. For a short guide to picking one, read `plugins/research-suite/SKILL.md`.

## Requirements

- Python 3. Fetching from Apple, Spotify, RSS, and App Store reviews uses only the standard library.
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on `PATH`, only for YouTube URLs (`brew install yt-dlp` or `pipx install yt-dlp`).
- `google-api-python-client` and `google-auth`, only for `review-scout`'s Android/Play Store path. That path works for your own app only and needs a service account. iOS review mining needs nothing extra.

## Install

### Claude Code plugin (recommended for Claude Code)

```
/plugin marketplace add OrenSegal/signal-skills
/plugin install signal-scout@oren-signal-skills
/plugin install podcast@oren-signal-skills
/plugin install review-scout@oren-signal-skills
/plugin install ideation@oren-signal-skills
/plugin install research-suite@oren-signal-skills
/plugin install signal-outreach@oren-signal-skills
```

Each plugin is standalone, so install only the ones you want. Invoke them as `/podcast`, `/review-scout`, `/ideation`, `/signal-scout`, `/research-suite`, and `/signal-outreach`. No `plugin:skill` prefix is needed because each plugin holds a single skill.

### Codex CLI

Codex has no plugin or marketplace layer, only skill folders. Copy the ones you want into your global skills folder:

```
git clone https://github.com/OrenSegal/signal-skills /tmp/signal-skills
cp -r /tmp/signal-skills/plugins/{podcast,review-scout,ideation,signal-scout,research-suite,signal-outreach} ~/.codex/skills/
```

Codex reads global skills from `~/.codex/skills/<name>/SKILL.md` (see [developers.openai.com/codex/skills](https://developers.openai.com/codex/skills)). The npx installer below also detects `~/.codex` and writes there.

### skills.sh

```
npx skills add OrenSegal/signal-skills
```

### npm / npx

```
npx signal-skills
```

The installer checks which of `~/.claude` and `~/.codex` exist and copies all six skills into each one it finds. If neither exists yet, it falls back to `~/.claude/skills`. Re-running is safe: it never overwrites a `config.json` you've customized.

## Usage

Once installed, describe what you want in plain language and the skill picks the right path:

```
mine https://podcasts.apple.com/us/podcast/.../id123456 for takeaways on pricing
what have I mined so far about AI agent pricing?
watch this show and check my subscriptions weekly
who's actually been right about model costs, score it
what are reviews saying about the app since the last release?
what should we build next based on everything we've mined?
```

## Repo layout

```
plugins/podcast/          resolve/mine podcasts (SKILL.md, ledger.py, resolve.py, sources.md)
plugins/review-scout/     mine app/store/web reviews (SKILL.md, ledger.py, resolve.py)
plugins/ideation/         findings -> prioritized build proposals (SKILL.md, ledger.py)
plugins/signal-scout/     shared report renderer (SKILL.md, render_report.py, template.html)
plugins/research-suite/   router/map skill for the mining/ideation/reporting skills (SKILL.md)
plugins/signal-outreach/  turn a signal-scout report into outreach/briefs/pitches (SKILL.md, scripts/generate_outreach.py)
.claude-plugin/marketplace.json   marketplace manifest for all six Claude Code plugins
bin/install.js            npx entry point, installs into Claude Code and/or Codex CLI
```

## Development

`plugins/signal-scout` holds the single authored copy of `render_report.py` and `template.html`. `podcast`, `review-scout`, and `ideation` each ship a generated copy of those two files instead of a symlink or runtime import. The reason: `/plugin install <name>@oren-signal-skills` fetches only that plugin's directory, so a cross-plugin reference resolves to nothing (this broke once).

After editing the `signal-scout` source, run `scripts/sync-shared-files.sh` to regenerate the three copies. CI runs `scripts/sync-shared-files.sh --check` so a hand-edited copy can't drift unnoticed.

## License

MIT
