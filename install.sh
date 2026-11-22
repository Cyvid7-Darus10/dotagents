#!/usr/bin/env bash
# Install this agent setup by symlinking it into ~/.claude (plus Codex/Gemini when present).
# Symlinks mean edits in the repo apply live and never drift. Anything replaced is backed up.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BACKUP_DIR="$CLAUDE_DIR/backups/pre-install-$(date +%Y%m%d-%H%M%S)"
DRY_RUN=false
WITH_PLUGINS=false
WITH_SOUNDS=false
WITH_ADHD=false
WITH_NOTES_HOOK=true
NO_PROMPT=false
CHOSE_PLUGINS=false  # set when a flag decided it, so we don't ask
CHOSE_ADHD=false
SKILLS=""   # comma-separated; empty = all
ADHD_PLUGIN="i-have-adhd@i-have-adhd"

usage() {
  cat <<EOF
Usage: ./install.sh [--dry-run] [--status] [--skills a,b,c] [--plugins|--no-plugins] [--adhd|--no-adhd]
                    [--no-notes-hook] [--sounds] [--no-prompt]

In a terminal it asks about the opt-in parts, shows what is on and off, and offers to start
the cleanup audit. --no-prompt (or no terminal) takes the defaults: nothing opt-in, no audit.
  --status        show what is on and off, change nothing

Installs (symlinks):
  global/AGENTS.md   -> ~/.claude/AGENTS.md, ~/.codex/AGENTS.md, ~/.gemini/GEMINI.md
  global/CLAUDE.md   -> ~/.claude/CLAUDE.md (imports AGENTS.md)
  skills/*           -> ~/.claude/skills/ (and ~/.agents/skills/ if it exists)
  agents/*, commands/* -> ~/.claude/agents/, ~/.claude/commands/
  rules/<lang>/      -> ~/.claude/rules/<lang>/ (path-scoped)
Configures:
  personal_docs/ in the global git excludes file
  settings.json: cleanupPeriodDays=90 (if unset), permission deny list (merged)
  Claude Code SessionStart hook: prints the project's personal_docs brief (skip: --no-notes-hook)
Opt-in:
  --plugins i-have-adhd plugin (on demand) + context7 MCP server (pinned)
  --sounds  macOS notification sounds on Stop/Notification
Choices:
  --skills a,b,c  link only these skills (default: all in skills/)
  --adhd          install, enable and turn on i-have-adhd for every session (+~2.5k tokens/session)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --status) exec python3 -I "$REPO/scripts/status.py" "$REPO" "$CLAUDE_DIR" ;;
    --plugins) WITH_PLUGINS=true; CHOSE_PLUGINS=true ;;
    --no-plugins) WITH_PLUGINS=false; CHOSE_PLUGINS=true ;;
    --hooks) echo "--hooks was removed: the hooks added output instead of trimming it (docs/EXPERIMENTS.md)." >&2 ;;
    --sounds) WITH_SOUNDS=true ;;
    --adhd) WITH_ADHD=true; CHOSE_ADHD=true ;;
    --no-adhd) WITH_ADHD=false; CHOSE_ADHD=true ;;
    --no-prompt) NO_PROMPT=true ;;
    --no-notes-hook) WITH_NOTES_HOOK=false ;;
    --skills) SKILLS="${2:?--skills needs a comma-separated list}"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
  shift
done

# Questions read from the terminal, so they also work under `curl ... | bash`.
INTERACTIVE=false
if ! $NO_PROMPT && [ -t 1 ] && (: </dev/tty) 2>/dev/null; then INTERACTIVE=true; fi

# ask QUESTION DEFAULT(y|n): true when the answer is yes.
ask() {
  local reply hint="[y/N]"
  [ "$2" = y ] && hint="[Y/n]"
  printf '%s %s ' "$1" "$hint"
  read -r reply </dev/tty || reply=""
  [[ "${reply:-$2}" =~ ^[Yy] ]]
}

choose_options() {
  $INTERACTIVE || return 0
  echo "A few choices first (Enter takes the default):"
  if ! $CHOSE_PLUGINS; then
    if ask "  Add context7 (up-to-date library docs) and i-have-adhd on demand (/i-have-adhd)?" y; then WITH_PLUGINS=true; fi
  fi
  if ! $CHOSE_ADHD; then
    if ask "  Turn on ADHD mode in every session? Short, focused replies; ~2.5k tokens per session." n; then WITH_ADHD=true; fi
  fi
  echo
}

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
  retire_common_rules
}

# Common rules from earlier versions are folded into global/AGENTS.md; an old copy would
# load twice. Only those known files go to the backup. Any rule the user wrote themselves
# moves up to ~/.claude/rules/ so it keeps loading.
FOLDED_RULES="coding-style git-workflow multi-repo-consistency security testing agents hooks patterns performance development-workflow"
retire_common_rules() {
  local common="$CLAUDE_DIR/rules/common" rule name
  [ -d "$common" ] && [ ! -L "$common" ] || return 0
  ensure_dir "$BACKUP_DIR/.claude/rules"
  run cp -R "$common" "$BACKUP_DIR/.claude/rules/common"
  for rule in "$common"/*.md; do
    [ -e "$rule" ] || continue
    name="$(basename "$rule" .md)"
    if [[ " $FOLDED_RULES " == *" $name "* ]]; then
      run rm "$rule"
    elif [ -e "$CLAUDE_DIR/rules/$name.md" ]; then
      say "kept ~/.claude/rules/common/$name.md (a rules/$name.md already exists)"
      continue
    else
      run mv "$rule" "$CLAUDE_DIR/rules/$name.md"
      say "kept your rule: moved rules/common/$name.md to rules/$name.md"
    fi
  done
  if $DRY_RUN || [ -z "$(ls -A "$common" 2>/dev/null)" ]; then run rmdir "$common"; fi
  say "retired ~/.claude/rules/common (now in AGENTS.md; copy in backup)"
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
  if [ -f "$CLAUDE_DIR/settings.json" ]; then
    ensure_dir "$BACKUP_DIR/.claude"
    run cp "$CLAUDE_DIR/settings.json" "$BACKUP_DIR/.claude/settings.json"
    say "backed up ~/.claude/settings.json before merging"
  fi
  local flags=()
  $WITH_SOUNDS && flags+=(--sounds)
  if $WITH_NOTES_HOOK && { [ -z "$SKILLS" ] || [[ ",$SKILLS," == *,project-notes,* ]]; }; then flags+=(--notes-hook); fi
  $DRY_RUN && flags+=(--dry-run)
  python3 -I "$REPO/scripts/merge_settings.py" "$REPO/settings.json" "$CLAUDE_DIR/settings.json" "${flags[@]}"
  if $WITH_SOUNDS; then link "$REPO/sounds" "$CLAUDE_DIR/sounds"; fi
}

# Install i-have-adhd if missing, and switch it on if it was disabled.
install_adhd_plugin() {
  local listing
  listing="$(claude plugin list 2>/dev/null || true)"
  if ! grep -q "$ADHD_PLUGIN" <<<"$listing"; then
    run claude plugin marketplace add ayghri/i-have-adhd
    run claude plugin install "$ADHD_PLUGIN"
  elif grep -A3 "$ADHD_PLUGIN" <<<"$listing" | grep -q disabled; then
    run claude plugin enable "$ADHD_PLUGIN"
    say "i-have-adhd was installed but disabled; enabled it"
  else
    say "i-have-adhd already installed and enabled"
  fi
}

have_claude() {
  command -v claude >/dev/null 2>&1 && return 0
  say "claude CLI not found; skipping. See docs/TOOLKIT.md for manual installs."
  return 1
}

install_adhd() {
  echo "ADHD mode (every session)"
  have_claude || return 0
  install_adhd_plugin
  run touch "$CLAUDE_DIR/.i-have-adhd-always"
  say "always-on flag set: $CLAUDE_DIR/.i-have-adhd-always"
}

install_plugins() {
  echo "Plugins and MCP"
  have_claude || return 0
  $WITH_ADHD || install_adhd_plugin
  if claude mcp get context7 >/dev/null 2>&1; then
    say "context7 already registered"
  else
    run claude mcp add --scope user context7 -- npx -y @upstash/context7-mcp@4.5.1
  fi
}

# The installer only adds. Cleanup is the audit, which needs the user's approval per change.
offer_audit() {
  echo
  echo "Installing does not remove anything. Unused MCP servers, plugins and skills stay until"
  echo "the cleanup audit runs. It changes nothing until you approve its plan."
  if $INTERACTIVE && ! $DRY_RUN && command -v claude >/dev/null 2>&1 \
    && ask "Start the cleanup audit now? (opens Claude in this repo)" y; then
    cd "$REPO"
    exec claude "Audit my setup."
  fi
  echo "Run it later: cd \"$REPO\" && claude \"Audit my setup.\""
}

main() {
  $DRY_RUN && echo "Dry run: nothing will change."
  choose_options
  install_global_instructions
  install_components
  install_git_excludes
  install_settings
  if $WITH_ADHD; then install_adhd; fi
  if $WITH_PLUGINS; then install_plugins; fi
  echo
  [ -d "$BACKUP_DIR" ] && echo "Backups: $BACKUP_DIR"
  if ! $DRY_RUN; then
    echo
    python3 -I "$REPO/scripts/status.py" "$REPO" "$CLAUDE_DIR"
  fi
  echo
  echo "Restart your agent so the changes load, then run /context to see the startup cost."
  echo "Check again any time: ./install.sh --status"
  offer_audit
}

main
