#!/usr/bin/env bash
# Link the art-to-Phlex kit's skills and Claude Code subagents into a project.
#
#   ./install.sh [--force] <project-dir>
#
# Creates symlinks, so a `git pull` in the kit updates every project that uses it:
#   <project>/.agents/skills/<skill>   (Codex, Antigravity, other AGENTS.md-aware tools)
#   <project>/.claude/skills/<skill>   (Claude Code)
#   <project>/.claude/agents/<agent>.md
#   <project>/.claude/settings.local.json  (the kit's permission rules; only if absent)
# In a git repository the links are also added to .git/info/exclude, so the experiment
# repository's status stays clean and nothing is committed by accident.
#
# An existing file or directory at a link path stops the install unless it is already a
# link into this kit. --force replaces it. An existing settings.local.json is never replaced.
# A link path whose parent directory resolves outside the project is refused.
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
inside_project() { # inside_project <relative path>: its parent must resolve inside the project
  local parent="$project/$(dirname -- "$1")" existing
  existing="$parent"
  while [[ ! -e "$existing" && ! -L "$existing" ]]; do existing="$(dirname -- "$existing")"; done
  existing="$(readlink -f -- "$existing")" || return 1
  [[ "$existing" == "$project" || "$existing" == "$project"/* ]]
}
link() { # link <target> <relative link path>
  local dest="$project/$2"
  if ! inside_project "$2"; then
    echo "install.sh: a parent of $2 is a symbolic link that leads out of the project; not linking" >&2
    exit 1
  fi
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

# Check every parent before making any link, so a refusal leaves the project unchanged.
for parent in .agents/skills .claude/skills .claude/agents; do
  if ! inside_project "$parent/x"; then
    echo "install.sh: $parent is or sits under a symbolic link that leads out of the project; nothing linked" >&2
    exit 1
  fi
done

for skill in "$kit"/skills/*/; do
  name="$(basename -- "$skill")"
  link "${skill%/}" ".agents/skills/$name"
  link "${skill%/}" ".claude/skills/$name"
done
for agent in "$kit"/agents/*.md; do
  link "$agent" ".claude/agents/$(basename -- "$agent")"
done

settings_note=""
local_settings=".claude/settings.local.json"
if [[ -L "$project/$local_settings" && "$(readlink -- "$project/$local_settings")" == "$kit"/* ]]; then
  : # already linked by an earlier run
elif [[ -e "$project/$local_settings" || -L "$project/$local_settings" ]]; then
  settings_note="WARNING: $local_settings already exists and was not changed. Merge the
\"permissions\" block from $kit/.claude/settings.json into it, or the kit's deny and ask
rules do not apply in this project."
else
  link "$kit/.claude/settings.json" "$local_settings"
fi

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
if [[ -n "$settings_note" ]]; then
  echo
  echo "$settings_note" >&2
fi
