#!/usr/bin/env bash
# SSOT sync: plugins/signal-report/{render_report.py,template.html} is the one
# authored copy. podcast/ideation/review-scout each need their own physical
# copy so they install standalone via `/plugin install <name>@marketplace`
# (that path fetches only one plugin dir, so a symlink or cross-plugin import
# to signal-report resolves to nothing - this already broke once, see git log).
# This script is the generator half of that trade-off: never hand-edit the
# copies, always regenerate from signal-report, and --check gates CI so a
# hand-edited copy can't silently drift from the source.
# analytics-check.md (authored in podcast, copied to review-scout) is covered
# the same way.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# "<source plugin>:<file>:<consumer plugins, space-separated>"
# analytics-check.md is authored in podcast and copied to review-scout for the
# same standalone-install reason.
SHARED=(
  "signal-report:render_report.py:podcast ideation review-scout"
  "signal-report:template.html:podcast ideation review-scout"
  "podcast:analytics-check.md:review-scout"
)

check_only=false
if [[ "${1:-}" == "--check" ]]; then
  check_only=true
fi

drift=0
for entry in "${SHARED[@]}"; do
  IFS=: read -r source file consumers <<<"$entry"
  src="$ROOT/plugins/$source/$file"
  for consumer in $consumers; do
    dest="$ROOT/plugins/$consumer/$file"
    if [[ ! -f "$dest" ]] || ! diff -q "$src" "$dest" >/dev/null 2>&1; then
      if $check_only; then
        echo "DRIFT: plugins/$consumer/$file does not match plugins/$source/$file"
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
  echo "OK: all generated copies match their source."
fi
