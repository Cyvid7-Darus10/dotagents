#!/bin/bash
# One-line installer for dot-agent.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dot-agent/main/setup.sh | bash
#
# Pass flags through to install.sh:
#   curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dot-agent/main/setup.sh | bash -s -- --skills humanizer,project-notes,setup-audit
#   curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dot-agent/main/setup.sh | bash -s -- --skills humanizer,project-notes,setup-audit
#   curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dot-agent/main/setup.sh | bash -s -- --dry-run
#
# Environment overrides:
#   DOT_AGENT_REPO  Git URL to clone (default: this repo on GitHub)
#   DOT_AGENT_REF   Branch/tag/commit to check out (default: main)
#   DOT_AGENT_SRC   Where to clone to (default: $HOME/.local/share/dot-agent)

set -euo pipefail

REPO="${DOT_AGENT_REPO:-https://github.com/cyruspastelero/dot-agent.git}"
REF="${DOT_AGENT_REF:-main}"
DEST="${DOT_AGENT_SRC:-$HOME/.local/share/dot-agent}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

if ! command -v git >/dev/null 2>&1; then
  echo -e "${RED}Error: git is required. Install git and re-run.${NC}" >&2
  exit 1
fi

if [ -d "$DEST/.git" ]; then
  echo -e "${YELLOW}Updating existing clone at $DEST${NC}"
  git -C "$DEST" fetch --quiet origin "$REF"
  git -C "$DEST" checkout --quiet "$REF"
  git -C "$DEST" reset --hard --quiet "origin/$REF" 2>/dev/null || true
else
  echo -e "${GREEN}Cloning $REPO → $DEST${NC}"
  mkdir -p "$(dirname "$DEST")"
  git clone --depth 1 --branch "$REF" --quiet "$REPO" "$DEST"
fi

cd "$DEST"
chmod +x install.sh
exec bash install.sh "$@"
