<div align="center">

# dotagents

**Dotfiles for coding agents.** One lean setup for Claude Code, Codex, Gemini CLI and Cursor, plus a hygiene check that trims what you don't use.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Measured](https://img.shields.io/badge/claims-measured-2ea44f)](docs/EXPERIMENTS.md)

</div>

Every connector, plugin and skill you've ever tried loads into every session before you type. The agent starts with less room and picks the wrong tools. dotagents gives you:

- **A setup audit.** It finds unused, failing, duplicate and never-signed-in connectors, plugins and skills, then removes them once you approve. On one setup it cut startup by 14%. → [docs/AUDIT.md](docs/AUDIT.md)
- **One instruction file for every agent.** [`global/AGENTS.md`](global/AGENTS.md) is linked into each one, so they never drift apart.
- **Shared project notes.** A private `personal_docs/` folder per project that every agent reads and updates. → [docs/PERSONAL_DOCS.md](docs/PERSONAL_DOCS.md)

## Quick start

```bash
git clone https://github.com/cyruspastelero/dotagents.git
cd dotagents
claude        # or: codex, gemini. This starts the audit.
```

Or install without the audit. It only adds files and removes nothing:

```bash
./install.sh --dry-run    # preview
./install.sh              # install; backs up anything it replaces
```

Flags, what gets linked where, and how to undo: [docs/INSTALL.md](docs/INSTALL.md).

## Docs

| | |
|---|---|
| [AUDIT.md](docs/AUDIT.md) | What the hygiene check finds, its phases, results |
| [INSTALL.md](docs/INSTALL.md) | Flags, linked paths, what's inside, undo |
| [PERSONAL_DOCS.md](docs/PERSONAL_DOCS.md) | The per-project notes convention |
| [TOOLKIT.md](docs/TOOLKIT.md) | Other tools to reach for, and when not to |
| [CONTEXT.md](docs/CONTEXT.md) | Context budget playbook: measure and trim |
| [EXPERIMENTS.md](docs/EXPERIMENTS.md) | Measurements behind every claim |

## Contributing

Keep it lean: every addition costs every user context in every session. A new tool needs a row in [TOOLKIT.md](docs/TOOLKIT.md), and a new claim needs a measurement in [EXPERIMENTS.md](docs/EXPERIMENTS.md). Run `./install.sh --dry-run` and `python3 -I skills/setup-audit/scripts/inventory.py` before opening a PR.

## Credits

Started as a fork of [Everything Claude Code](https://github.com/affaan-m/ECC), then cut down to what measurably helps. Ideas from [superpowers](https://github.com/obra/superpowers), [i-have-adhd](https://github.com/ayghri/i-have-adhd) and [caveman](https://github.com/JuliusBrussee/caveman).

MIT © Cyrus David Pastelero
