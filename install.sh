#!/usr/bin/env bash
# Install this agent setup by symlinking it into ~/.claude (plus Codex/Gemini when present).
# Symlinks mean edits in the repo apply live and never drift. Anything replaced is backed up.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BACKUP_DIR="$CLAUDE_DIR/backups/pre-install-$(date +%Y%m%d-%H%M%S)"
DRY_RUN=false
WITH_PLUGINS=true
WITH_HOOKS=false
WITH_SOUNDS=false
WITH_ADHD=false
SKILLS=""   # comma-separated; empty = all

usage() {
  cat <<EOF
Usage: ./install.sh [--dry-run] [--skills a,b,c] [--no-plugins] [--adhd] [--hooks] [--sounds]

Installs (symlinks):
  global/AGENTS.md   -> ~/.claude/AGENTS.md, ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md
  global/CLAUDE.md   -> ~/.claude/CLAUDE.md (imports AGENTS.md)
  skills/*           -> ~/.claude/skills/ (and ~/.agents/skills/ if it exists)
  agents/*, commands/* -> ~/.claude/agents/, ~/.claude/commands/
  rules/<lang>/      -> ~/.claude/rules/<lang>/ (path-scoped)
Configures:
  personal_docs/ in the global git excludes file
  settings.json: cleanupPeriodDays=90 (if unset), permission deny list (merged)
  plugins i-have-adhd + context7 MCP (skip: --no-plugins)
Opt-in:
  --hooks   token-saving Read/PostToolUse hooks (needs Node 18+)
  --sounds  macOS notification sounds on Stop/Notification
Choices:
  --skills a,b,c  link only these skills (default: all in skills/)
  --adhd          turn on i-have-adhd for every session (+~2.5k tokens/session)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --no-plugins) WITH_PLUGINS=false ;;
    --hooks) WITH_HOOKS=true ;;
    --sounds) WITH_SOUNDS=true ;;
    --adhd) WITH_ADHD=true ;;
    --skills) SKILLS="${2:?--skills needs a comma-separated list}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

say() { printf '  %s\n' "$*"; }
run() { if $DRY_RUN; then say "[dry-run] $*"; else "$@"; fi; }
ensure_dir() { $DRY_RUN || mkdir -p "$1"; }

# link SRC DEST: replace a symlink, back up a real file/dir, then link.
link() {
  local src="$1" dest="$2"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then return 0; fi
  ensure_dir "$(dirname "$dest")"
  if [ -L "$dest" ]; then
    run rm "$dest"
  elif [ -e "$dest" ]; then
    local rel="${dest#"$HOME"/}"
    ensure_dir "$BACKUP_DIR/$(dirname "$rel")"
    run mv "$dest" "$BACKUP_DIR/$rel"
    say "backed up ~/$rel"
  fi
  run ln -s "$src" "$dest"
  say "linked ~/${dest#"$HOME"/}"
}

install_global_instructions() {
  echo "Global instructions"
  link "$REPO/global/AGENTS.md" "$CLAUDE_DIR/AGENTS.md"
  link "$REPO/global/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
  if [ -d "$HOME/.codex" ]; then link "$REPO/global/AGENTS.md" "$HOME/.codex/AGENTS.md"; fi
  if [ -d "$HOME/.gemini" ]; then link "$REPO/global/AGENTS.md" "$HOME/.gemini/GEMINI.md"; fi
  # Common rules are folded into global/AGENTS.md; an old copy would load twice.
  if [ -d "$CLAUDE_DIR/rules/common" ] && [ ! -L "$CLAUDE_DIR/rules/common" ]; then
    ensure_dir "$BACKUP_DIR/.claude/rules"
    run mv "$CLAUDE_DIR/rules/common" "$BACKUP_DIR/.claude/rules/common"
    say "moved ~/.claude/rules/common to backup (now in AGENTS.md)"
  fi
}

# Print the skill names to install: all, or the validated --skills list.
selected_skills() {
  if [ -z "$SKILLS" ]; then
    for dir in "$REPO"/skills/*/; do basename "$dir"; done
    return 0
  fi
  local name
  for name in ${SKILLS//,/ }; do
    if [ -d "$REPO/skills/$name" ]; then echo "$name"; else echo "  unknown skill: $name (skipped)" >&2; fi
  done
}

install_components() {
  echo "Skills, agents, commands, rules"
  local dir name
  for name in $(selected_skills); do
    dir="$REPO/skills/$name"
    link "$dir" "$CLAUDE_DIR/skills/$name"
    if [ -d "$HOME/.agents/skills" ]; then link "$dir" "$HOME/.agents/skills/$name"; fi
  done
  for f in "$REPO"/agents/*.md; do link "$f" "$CLAUDE_DIR/agents/$(basename "$f")"; done
  for f in "$REPO"/commands/*.md; do link "$f" "$CLAUDE_DIR/commands/$(basename "$f")"; done
  for dir in "$REPO"/rules/*/; do link "${dir%/}" "$CLAUDE_DIR/rules/$(basename "$dir")"; done
}

install_git_excludes() {
  echo "Global git excludes"
  local excludes
  excludes="$(git config --global core.excludesFile || true)"
  if [ -z "$excludes" ]; then
    excludes="$HOME/.config/git/ignore"
    run git config --global core.excludesFile "$excludes"
  fi
  excludes="${excludes/#\~/$HOME}"
  if grep -qxF 'personal_docs/' "$excludes" 2>/dev/null; then
    say "personal_docs/ already ignored in $excludes"
  else
    ensure_dir "$(dirname "$excludes")"
    if $DRY_RUN; then say "[dry-run] append personal_docs/ to $excludes"; else printf '\n# Private per-project agent notes\npersonal_docs/\n' >> "$excludes"; fi
    say "personal_docs/ added to $excludes"
  fi
}

install_settings() {
  echo "Settings"
  local flags=()
  $WITH_HOOKS && flags+=(--hooks)
  $WITH_SOUNDS && flags+=(--sounds)
  $DRY_RUN && flags+=(--dry-run)
  python3 -I "$REPO/scripts/merge_settings.py" "$REPO/settings.json" "$CLAUDE_DIR/settings.json" "${flags[@]}"
  if $WITH_HOOKS; then
    for f in "$REPO"/hooks/*.mjs; do link "$f" "$CLAUDE_DIR/hooks/$(basename "$f")"; done
  fi
  if $WITH_SOUNDS; then link "$REPO/sounds" "$CLAUDE_DIR/sounds"; fi
  if $WITH_ADHD; then run touch "$CLAUDE_DIR/.i-have-adhd-always"; fi
}

install_plugins() {
  echo "Plugins and MCP"
  if ! command -v claude >/dev/null 2>&1; then
    say "claude CLI not found; skipping. See docs/TOOLKIT.md for manual installs."
    return 0
  fi
  if claude plugin list 2>/dev/null | grep -q 'i-have-adhd'; then
    say "i-have-adhd already installed"
  else
    run claude plugin marketplace add ayghri/i-have-adhd
    run claude plugin install i-have-adhd@i-have-adhd
  fi
  if claude mcp get context7 >/dev/null 2>&1; then
    say "context7 already registered"
  else
    run claude mcp add --scope user context7 -- npx -y @upstash/context7-mcp@latest
  fi
}

main() {
  $DRY_RUN && echo "Dry run: nothing will change."
  install_global_instructions
  install_components
  install_git_excludes
  install_settings
  $WITH_PLUGINS && install_plugins
  echo
  [ -d "$BACKUP_DIR" ] && echo "Backups: $BACKUP_DIR"
  echo "Done. Restart your agent, then run /context to see the startup cost."
}

main
