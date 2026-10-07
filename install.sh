#!/usr/bin/env bash
# Link the art-to-Phlex kit's skills and Claude Code subagents into a project.
#
#   ./install.sh [--force] <project-dir>
#
# Creates symlinks, so a `git pull` in the kit updates every project that uses it:
#   <project>/.agents/skills/<skill>   (Codex, Antigravity, other AGENTS.md-aware tools)
#   <project>/.claude/skills/<skill>   (Claude Code)
#   <project>/.claude/agents/<agent>.md
# In a git repository the links are also added to .git/info/exclude, so the experiment
# repository's status stays clean and nothing is committed by accident.
#
# An existing file or directory at a link path stops the install unless it is already a
# link into this kit. --force replaces it.
set -euo pipefail
shopt -s nullglob

force=0
if [[ "${1:-}" == --force ]]; then force=1; shift; fi

kit="$(CDPATH='' cd -- "$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")" >/dev/null && pwd -P)"
project="$(CDPATH='' cd -- "${1:?usage: install.sh [--force] <project-dir>}" >/dev/null && pwd -P)"

if [[ "$project" == "$kit" ]]; then
  echo "install.sh: the target is the kit itself; it already has its own links" >&2
  exit 1
fi

added=()
link() { # link <target> <relative link path>
  local dest="$project/$2"
  if [[ -L "$dest" ]]; then
    local current
    current="$(readlink -- "$dest")"
    if [[ "$current" != "$kit"/* && $force -eq 0 ]]; then
      echo "install.sh: $2 is a link to $current, not into the kit; use --force to replace" >&2
      exit 1
    fi
    rm -- "$dest"
  elif [[ -e "$dest" ]]; then
    if [[ $force -eq 0 ]]; then
      echo "install.sh: $2 already exists; use --force to replace it" >&2
      exit 1
    fi
    rm -rf -- "$dest"
  fi
  mkdir -p -- "$(dirname -- "$dest")"
  ln -s -- "$1" "$dest"
  added+=("$2")
  echo "linked $2 -> $1"
}

for skill in "$kit"/skills/*/; do
  name="$(basename -- "$skill")"
  link "${skill%/}" ".agents/skills/$name"
  link "${skill%/}" ".claude/skills/$name"
done
for agent in "$kit"/agents/*.md; do
  link "$agent" ".claude/agents/$(basename -- "$agent")"
done

if exclude="$(git -C "$project" rev-parse --git-path info/exclude 2>/dev/null)"; then
  [[ "$exclude" == /* ]] || exclude="$project/$exclude"
  # Exclude patterns are anchored at the repository root, so a project that is a
  # subdirectory of the repository needs its prefix.
  prefix="$(git -C "$project" rev-parse --show-prefix)"
  mkdir -p -- "$(dirname -- "$exclude")"
  touch -- "$exclude"
  for path in ${added[@]+"${added[@]}"}; do
    grep -qxF "/$prefix$path" "$exclude" || echo "/$prefix$path" >>"$exclude"
  done
  echo "listed the links in $exclude"
fi

echo
printf 'Scripts are referenced as $KIT/skills/...; set: export KIT=%q\n' "$kit"
