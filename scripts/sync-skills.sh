#!/usr/bin/env bash
# Copy canonical skills/ into the agent skill folders (real files, not symlinks).
#   scripts/sync-skills.sh           # write copies
#   scripts/sync-skills.sh --check   # exit 1 if a copy differs or is missing
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CANON="$ROOT/skills"
DESTS=(.claude/skills .cursor/skills .codex/skills .agents/skills)
CHECK=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK=1
elif [[ "${1:-}" != "" ]]; then
  echo "usage: $0 [--check]" >&2
  exit 1
fi

shopt -s nullglob
skills=("$CANON"/*/SKILL.md)
if [[ ${#skills[@]} -eq 0 ]]; then
  echo "no skills in $CANON" >&2
  exit 1
fi

status=0
for skill in "${skills[@]}"; do
  name=$(basename "$(dirname "$skill")")
  for dest in "${DESTS[@]}"; do
    target="$ROOT/$dest/$name/SKILL.md"
    if [[ "$CHECK" -eq 1 ]]; then
      if ! cmp -s "$skill" "$target"; then
        echo "out of sync: $dest/$name/SKILL.md" >&2
        status=1
      fi
    else
      mkdir -p "$(dirname "$target")"
      cp "$skill" "$target"
      echo "wrote $dest/$name/SKILL.md"
    fi
  done
done
exit "$status"
