# Hooks

Optional token-saving hooks, installed with `./install.sh --hooks` (needs Node 18+). They are linked into `~/.claude/hooks/` and registered in `~/.claude/settings.json`. Nothing else is installed.

| File | Event | What it does |
|---|---|---|
| `pre-read.mjs` | PreToolUse (Read) | Blocks re-reading a file already in context (same path and range) |
| `compress.mjs` | PostToolUse | Compresses noisy Bash, Grep and Glob output before it enters context |

Remove one by deleting its entry from `settings.json` and its link in `~/.claude/hooks/`.
