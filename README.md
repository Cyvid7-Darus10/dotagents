<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
  <img src="assets/logo-light.svg" alt="dot-agent logo: one dot in the middle with four smaller dots around it" width="96" height="96">
</picture>

# dot-agent

**Dotfiles for coding agents.** One lean setup for Claude Code, Codex, Gemini CLI and Cursor, plus a hygiene check that trims what you don't use.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Measured](https://img.shields.io/badge/claims-measured-2ea44f)](docs/EXPERIMENTS.md)

</div>

Connectors, plugins and skills you tried once stay installed, and each one loads into every session before you type. The agent starts with less room and picks the wrong tools. dot-agent gives you:

- **A setup audit.** It finds unused, failing, duplicate and never-signed-in connectors, plugins and skills, then removes them once you approve. On one setup it cut startup tokens by 11–14%. → [docs/AUDIT.md](docs/AUDIT.md)
- **One instruction file for every agent.** [`global/AGENTS.md`](global/AGENTS.md) is linked into Claude Code, Codex and Gemini CLI (pasted into Cursor), so they stay in sync.
- **Shared project notes.** A private `personal_docs/` folder per project that every agent reads and updates. → [docs/PERSONAL_DOCS.md](docs/PERSONAL_DOCS.md)

> [!IMPORTANT]
> **This is my own setup, and this is how it works for me.** The instructions, skills, deny list and defaults match how I work: macOS, mostly Claude Code, Swift, TypeScript and Python. They may not suit you. Read [`global/AGENTS.md`](global/AGENTS.md) before installing, run `./install.sh --dry-run` first, and change what doesn't fit. Installing never removes anything, and everything it replaces is backed up. Cleanup happens only in the audit, and only after you approve each change. Use it at your own risk; it comes with no warranty ([MIT](LICENSE)).

## Quick start

```bash
git clone https://github.com/cyruspastelero/dot-agent.git
cd dot-agent
claude        # or: codex, gemini. This starts the audit.
```

The audit reads first and changes nothing until you approve its plan. Measuring startup tokens costs a few cents to about $1 of API usage, and it asks before doing that.

Or install without the audit. It only adds files and removes nothing. It also adds a permission deny list to your settings; see [INSTALL.md](docs/INSTALL.md):

```bash
./install.sh --dry-run    # preview
./install.sh              # install; backs up anything it replaces, then offers the audit
./install.sh --status     # see what is on, what is off, and how to turn it on
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
