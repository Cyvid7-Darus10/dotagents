<div align="center">

# dotagents

**Dotfiles for coding agents.** One lean setup for Claude Code, Codex, Gemini CLI and Cursor. It includes a guided auditor that measures your current setup, explains it, and trims it with you.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Agents](https://img.shields.io/badge/works%20with-Claude%20Code%20·%20Codex%20·%20Gemini%20CLI%20·%20Cursor-111)](global/AGENTS.md)
[![Skills](https://img.shields.io/badge/skills-24-orange)](skills/)
[![Measured](https://img.shields.io/badge/claims-measured-2ea44f)](docs/EXPERIMENTS.md)

[Quick start](#quick-start) · [What the audit does](#what-the-audit-does) · [Results](#results) · [What's inside](#whats-inside) · [personal_docs](#personal_docs) · [Toolkit](docs/TOOLKIT.md) · [Experiments](docs/EXPERIMENTS.md)

</div>

---

## Why

Agent setups grow by accretion. You try a connector, a plugin, a skill pack, and they all stay. Each one is loaded into **every** session before you type: tool names, descriptions, injected rules. The agent starts with less room, compacts sooner and follows instructions less reliably. And each agent you use has its own config, so the instructions drift apart.

dotagents fixes both problems:

- **One source of truth.** A single [`global/AGENTS.md`](global/AGENTS.md) is linked into every agent, and the skills say when they apply. Edits in the repo go live through symlinks.
- **Shared project memory.** A private, git-ignored [`personal_docs/`](#personal_docs) folder in each project that every agent reads first and writes back to.
- **A guided audit.** [`setup-audit`](skills/setup-audit/SKILL.md) measures your setup, explains it in plain language, asks how you work, and proposes a reversible plan. It changes nothing until you approve.

## Quick start

```bash
git clone https://github.com/Cyvid7-Darus10/dotagents.git
cd dotagents
claude        # or: codex, gemini
```

Opening an agent in the repo starts **audit mode** ([`AGENTS.md`](AGENTS.md)). You can also skip the audit:

```bash
./install.sh --dry-run                 # preview every change
./install.sh                           # install everything (backs up whatever it replaces)
./install.sh --skills humanizer,verify-app,project-notes,setup-audit   # pick skills
```

| Flag | Effect |
|---|---|
| `--skills a,b,c` | Link only these skills (default: all) |
| `--adhd` | Turn on i-have-adhd for every session (costs ~2.5k tokens/session; off by default) |
| `--no-notes-hook` | Don't auto-load `personal_docs/` at Claude Code session start |
| `--no-plugins` | Skip installing the i-have-adhd plugin (on demand via `/i-have-adhd`) and the context7 MCP server |
| `--hooks` | Token-saving Read/PostToolUse hooks (needs Node 18+) |
| `--sounds` | macOS notification sounds |

## What the audit does

| Phase | What you see | Changes anything? |
|---|---|---|
| 1. Inventory | Scans connectors, MCP servers, plugins, skills, agents, rules and memory, plus your transcripts for what you actually use. Optionally measures startup tokens (you approve the few cents of API cost) | No |
| 2. Report | **"Your setup today":** startup cost, an inventory table, what costs the most (with evidence), what's working, caveats | No |
| 3. Interview | Up to 4 questions: what you build, which agents you use, output style, borderline items | No |
| 4. Plan | A table of change · why · expected effect · undo, plus the `install.sh --dry-run` output. One approval, and you can strike rows | No |
| 5. Apply | Archives (never deletes), disables, scopes to projects, installs your choices | Yes, with backups |
| 6. Verify | Re-measures and shows before/after numbers, how to work with the new setup, how to undo | No |

## Results

Measured on the setup this repo was built from (Claude Code 2.1.330, Opus 5.5). Method, raw runs and caveats are in [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

| What was changed | Startup tokens |
|---|---|
| Claude Code's own floor (system prompt + built-in tools) | ~35,400 |
| claude.ai connectors (15, several never signed in) | **+3.4k to +12.8k** headless; more in interactive sessions |
| i-have-adhd always-on injection | +2.5k |
| One framework plugin with 49 skills | +0.9k |
| Old config files vs. new (45→24 skills, 17→10 agents, 8.7 KB→4.5 KB always-on rules) | +0.25k |

Interactive sessions on the old setup started at a **median of 77.4k tokens** (11 sessions, from local transcripts).

What we learned: **connectors and always-on injections are where the tokens go.** Trimming skills and rules is worth doing for clarity and correctness (fewer wrong auto-picks, no "MUST BE USED" subagent spam, one source of truth), but it is not a token lever. We say so rather than oversell it.

## What's inside

```
dotagents/
├── AGENTS.md            ← instructions for agents opened in this repo (audit mode)
├── global/
│   ├── AGENTS.md        ← your global instructions, for every agent
│   └── CLAUDE.md        ← imports AGENTS.md + Claude-only extras
├── skills/              ← 24 skills, each says when it applies
│   ├── setup-audit/     ← the guided auditor (+ inventory.py, measure.py)
│   └── project-notes/   ← personal_docs convention, templates, notes.py
├── agents/  commands/   ← reviewers, tdd-guide, build fixer; /tdd /verify /ponytail…
├── rules/<lang>/        ← path-scoped: load only when matching files are touched
├── docs/                ← TOOLKIT, CONTEXT, EXPERIMENTS
├── hooks/               ← optional token-saving hooks (--hooks)
└── install.sh           ← symlink installer with dry-run and backups
```

| Where | What gets linked |
|---|---|
| Claude Code | `~/.claude/{CLAUDE.md, AGENTS.md, skills, agents, commands, rules}` |
| Codex | `~/.codex/AGENTS.md` (+ `~/.agents/skills/` if present) |
| Gemini CLI | `~/.gemini/GEMINI.md` |
| Cursor | Paste `global/AGENTS.md` into *Rules for AI* (Cursor has no global file) |

**Skills:** `setup-audit` and `project-notes`, plus `humanizer` (copy that doesn't read as machine-written), `verify-app` (per-feature coverage matrix and fix loop), `audit-app-design`, `shipping-ios-apps`, `appstore-release`, `marketing-screenshots`, `polar-checkout`, `backend-judgement`, `systematic-reasoning`, `photo-cull`, `ponytail`. The rest are reference patterns for Swift/SwiftUI, Python, Postgres, migrations and API design.

## personal_docs

Every project gets a private, git-ignored notebook that all your agents share. Agents read it first, resume unfinished work from it, and write back what they learn.

```
your-project/
└── personal_docs/        git-ignored via your global excludes file, never committed
    ├── README.md         read every session · ≤60 lines · focus + a "read when" map
    ├── work/             one file per unfinished task: plan · state · next step
    ├── runbook.md        ┐
    ├── gotchas.md        │ opened only when the task needs them
    ├── decisions.md      │ created on first entry, never as empty templates
    ├── architecture.md   │ every entry carries a source and a "verified" date
    ├── learnings.md      ┘
    ├── docs/             longer reference
    └── archive/          finished work, retired entries
```

| Design choice | Why |
|---|---|
| Only `README.md` is read every session | Each session pays for about 60 lines, not the whole folder |
| `work/` with a **Next** line per task | Any agent can resume cold, even in a different tool than yesterday |
| Source + `Verified:` date on each entry | Notes rot. Old entries get re-checked instead of trusted blindly |
| Created lazily, with size budgets | Empty or bloated notes get ignored. Small, real notes get read |
| Claude Code loads it automatically | A SessionStart hook runs `notes.py brief`. It prints nothing where there are no notes. Other agents follow the same rule from `AGENTS.md` |

`notes.py check` lints a project's notes: confirms they're git-ignored, flags entries older than 90 days, paths that no longer exist, files over budget, and anything that looks like a secret.

- **Why not `CLAUDE.md`?** It's committed and team-facing, and only one agent reads it. `personal_docs/` is private, structured, and shared by every agent you use.
- **Why not agent memory?** Agent memory is per tool and per user. It suits how you like to work. Project facts belong with the project.

## Toolkit: when to reach for what

| Situation | Use |
|---|---|
| Library or CLI syntax, version-specific APIs | [context7](https://github.com/upstash/context7) |
| Large or unfamiliar repo, "how does X reach Y?" | [graphify](https://github.com/safishamsi/graphify), per project |
| Symbol-level navigation in a big typed codebase | LSP plugins, or [serena](https://github.com/oraios/serena) |
| Very long session where replies dominate | [caveman](https://github.com/JuliusBrussee/caveman) `/ultracave`, on demand |
| You want an enforced plan → TDD process | [superpowers](https://github.com/obra/superpowers) |

Full guide, including when **not** to install each one: [docs/TOOLKIT.md](docs/TOOLKIT.md).

## Undo

- Every replaced file goes to `~/.claude/backups/pre-install-<timestamp>/`, and the path is printed at the end.
- Links are symlinks: `rm ~/.claude/skills/<name>` removes one and leaves the repo intact.
- The audit archives to `~/.claude/archive/` and never deletes.

## Contributing

Keep it lean. Every addition costs every user context in every session. A new tool needs a "use when / skip when" row in [TOOLKIT.md](docs/TOOLKIT.md). A new claim needs a measurement in [EXPERIMENTS.md](docs/EXPERIMENTS.md). Run `./install.sh --dry-run` and `python3 -I skills/setup-audit/scripts/inventory.py` before opening a PR.

## Credits

Started as a fork of [Everything Claude Code](https://github.com/affaan-m/ECC), then cut down to what measurably helps. Process ideas from [obra/superpowers](https://github.com/obra/superpowers). Output-style ideas from [i-have-adhd](https://github.com/ayghri/i-have-adhd) and [caveman](https://github.com/JuliusBrussee/caveman).

MIT © Cyrus David Pastelero
