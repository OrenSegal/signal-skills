#!/usr/bin/env python3
"""State store for the ideation skill: tracks proposals already made so a
fresh run doesn't re-propose the same idea every time.

Same shape as podcast/review-scout's ledger.py (deliberately) but NOT
shared/symlinked with either: `Path(__file__).resolve()` follows a symlink
back to the *other* skill's directory, silently writing this skill's state
into that one's config/state instead of its own. Keep this a real copy.

Nothing here calls an LLM or a Claude Code tool. This is plumbing the
orchestrating agent shells out to; AskUserQuestion / Artifact stay in
SKILL.md.

Layout:
  ~/.signal-skills/ideation/config.json     — persisted preferences
  ~/.signal-skills/ideation/state/ideas.json — one file, all proposals
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = "ideation"
# State lives outside the install folder: a plugin update installs into a new
# versioned folder, and Claude Code and Codex install into different homes.
DATA_DIR = Path(os.environ.get("SIGNAL_SKILLS_HOME") or Path.home() / ".signal-skills") / SKILL
CONFIG_PATH = DATA_DIR / "config.json"
IDEAS_PATH = DATA_DIR / "state" / "ideas.json"
# Where earlier versions kept state: next to this file.
LEGACY_DIRS = (ROOT, Path.home() / ".claude" / "skills" / SKILL, Path.home() / ".agents" / "skills" / SKILL)


def migrate_legacy(data_dir=None, legacy_dirs=None):
    """First run only: copy config.json and state/ from the first earlier
    location that has them. Copies, never moves, and does nothing once
    data_dir exists. Returns the folder copied from, or None."""
    data_dir = Path(data_dir or DATA_DIR)
    if data_dir.exists():
        return None
    for old in legacy_dirs or LEGACY_DIRS:
        old = Path(old)
        has_config, has_state = (old / "config.json").is_file(), (old / "state").is_dir()
        if not (has_config or has_state):
            continue
        data_dir.mkdir(parents=True)
        if has_config:
            shutil.copy2(old / "config.json", data_dir / "config.json")
        if has_state:
            shutil.copytree(old / "state", data_dir / "state")
        return old
    return None

STATUSES = {"proposed", "shipped", "rejected", "parked"}


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "idea"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def load_ideas():
    return load_json(IDEAS_PATH, {"ideas": {}})


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- config

def cmd_config_get(args):
    cfg = load_json(CONFIG_PATH, {})
    print(cfg.get(args.key, ""))


def cmd_config_set(args):
    cfg = load_json(CONFIG_PATH, {})
    cfg[args.key] = args.value
    save_json(CONFIG_PATH, cfg)
    print(f"{args.key}={args.value}")


# ----------------------------------------------------------------- ideas

def cmd_list(args):
    """Print all known ideas, optionally filtered by --status, so a fresh
    proposal pass can skip anything already proposed/shipped/rejected and
    only surface genuinely new ones."""
    ideas = load_ideas()["ideas"]
    out = []
    for slug, data in ideas.items():
        if args.status and data.get("status") != args.status:
            continue
        out.append({"slug": slug, **data})
    out.sort(key=lambda i: i.get("proposed_at", ""))
    print(json.dumps(out, indent=2))


def cmd_propose(args):
    """Record a new proposal. citations_json is a JSON array of short
    strings pointing back at the specific findings (from podcast/
    review-scout ledgers) that motivated this idea — an idea with no
    citation is a guess, not a finding-driven proposal."""
    slug = slugify(args.title)
    ideas = load_ideas()
    citations = json.loads(args.citations_json) if args.citations_json else []
    if slug in ideas["ideas"]:
        print(f"already proposed: {slug} (status={ideas['ideas'][slug]['status']})")
        return
    ideas["ideas"][slug] = {
        "title": args.title,
        "status": "proposed",
        "proposed_at": today(),
        "citations": citations,
        "note": args.note or "",
    }
    save_json(IDEAS_PATH, ideas)
    print(f"proposed {slug} ({len(citations)} citations)")


def cmd_set_status(args):
    if args.status not in STATUSES:
        print(f"invalid status: {args.status} (must be one of {sorted(STATUSES)})", file=sys.stderr)
        sys.exit(1)
    ideas = load_ideas()
    slug = slugify(args.title)
    if slug not in ideas["ideas"]:
        print(f"no such idea: {slug}", file=sys.stderr)
        sys.exit(1)
    ideas["ideas"][slug]["status"] = args.status
    ideas["ideas"][slug]["status_updated_at"] = today()
    save_json(IDEAS_PATH, ideas)
    print(f"{slug} -> {args.status}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("config-get")
    s.add_argument("key")
    s.set_defaults(func=cmd_config_get)

    s = sub.add_parser("config-set")
    s.add_argument("key")
    s.add_argument("value")
    s.set_defaults(func=cmd_config_set)

    s = sub.add_parser("list")
    s.add_argument("--status", default=None, choices=sorted(STATUSES))
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("propose")
    s.add_argument("--title", required=True)
    s.add_argument("--citations-json", default="[]")
    s.add_argument("--note", default="")
    s.set_defaults(func=cmd_propose)

    s = sub.add_parser("set-status")
    s.add_argument("--title", required=True)
    s.add_argument("--status", required=True)
    s.set_defaults(func=cmd_set_status)

    args = p.parse_args()
    migrate_legacy()
    args.func(args)


if __name__ == "__main__":
    main()
