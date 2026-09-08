#!/usr/bin/env bash
# SSOT sync: plugins/signal-scout/{render_report.py,template.html} is the one
# authored copy. podcast/ideation/review-scout each need their own physical
# copy so they install standalone via `/plugin install <name>@marketplace`
# (that path fetches only one plugin dir, so a symlink or cross-plugin import
# to signal-scout resolves to nothing - this already broke once, see git log).
# This script is the generator half of that trade-off: never hand-edit the
# copies, always regenerate from signal-scout, and --check gates CI so a
# hand-edited copy can't silently drift from the source.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT/plugins/signal-scout"
FILES=(render_report.py template.html)
CONSUMERS=(podcast ideation review-scout)

check_only=false
if [[ "${1:-}" == "--check" ]]; then
  check_only=true
fi

drift=0
for consumer in "${CONSUMERS[@]}"; do
  for file in "${FILES[@]}"; do
    src="$SRC_DIR/$file"
    dest="$ROOT/plugins/$consumer/$file"
    if [[ ! -f "$dest" ]] || ! diff -q "$src" "$dest" >/dev/null 2>&1; then
      if $check_only; then
        echo "DRIFT: plugins/$consumer/$file does not match plugins/signal-scout/$file"
        drift=1
      else
        cp "$src" "$dest"
        echo "synced  plugins/$consumer/$file"
      fi
    fi
  done
done

if $check_only; then
  if [[ $drift -ne 0 ]]; then
    echo ""
    echo "Run scripts/sync-shared-files.sh (no --check) to fix, then commit." >&2
    exit 1
  fi
  echo "OK: all consumer copies match plugins/signal-scout source."
fi
