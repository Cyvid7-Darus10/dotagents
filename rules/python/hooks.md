---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
# Python Hooks

> Extends the global `AGENTS.md` with Python-specific guidance.

## PostToolUse Hooks

Configure in `~/.claude/settings.json`:

- **black/ruff**: Auto-format `.py` files after edit
- **mypy/pyright**: Run type checking after editing `.py` files

## Warnings

- Warn about `print()` statements in edited files (use `logging` module instead)
