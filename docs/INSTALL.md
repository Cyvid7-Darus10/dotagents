# Install

`install.sh` symlinks this repo into your agents' config folders, so edits in the repo go live. It backs up anything it replaces. It only **adds** files: it removes nothing, so run the [audit](AUDIT.md) to clean up.

```bash
./install.sh --dry-run                 # preview every change
./install.sh                           # install everything
./install.sh --skills humanizer,verify-app,project-notes,setup-audit   # pick skills
```

One-line install, without cloning first (clones to `~/.local/share/dotagents`):

```bash
curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dotagents/main/setup.sh | bash
```

## Flags

| Flag | Effect |
|---|---|
| `--skills a,b,c` | Link only these skills (default: all) |
| `--adhd` | Turn on i-have-adhd for every session (~2.5k tokens per session; off by default) |
| `--no-notes-hook` | Don't auto-load `personal_docs/` when a Claude Code session starts |
| `--no-plugins` | Skip the i-have-adhd plugin and the context7 MCP server |
| `--hooks` | Token-saving Read/PostToolUse hooks (needs Node 18+) |
| `--sounds` | macOS notification sounds |

## What gets linked

| Agent | Where |
|---|---|
| Claude Code | `~/.claude/{CLAUDE.md, AGENTS.md, skills, agents, commands, rules}` |
| Codex | `~/.codex/AGENTS.md` (and `~/.agents/skills/` if it exists) |
| Gemini CLI | `~/.gemini/GEMINI.md` |
| Cursor | Paste `global/AGENTS.md` into *Rules for AI* (Cursor has no global file) |

It also adds `personal_docs/` to your global git excludes, and merges `settings.json` without overwriting your values: `cleanupPeriodDays`, a permission deny list, and the `personal_docs` startup hook.

Rule files in `~/.claude/rules/common/` from older versions are folded into `global/AGENTS.md`. Known ones go to the backup. Rules you wrote yourself move up to `~/.claude/rules/`, so they keep loading.

## What's inside

```
dotagents/
├── AGENTS.md          instructions for agents opened in this repo (audit mode)
├── global/            AGENTS.md for every agent; CLAUDE.md imports it + Claude extras
├── skills/            24 skills; setup-audit and project-notes are the core
├── agents/ commands/  reviewers, tdd-guide, build fixer; /tdd /verify /ponytail …
├── rules/<lang>/      path-scoped, load only for matching files
├── hooks/             optional token-saving hooks (--hooks)
└── docs/              these guides
```

The other skills: `humanizer`, `verify-app`, `audit-app-design`, `shipping-ios-apps`, `appstore-release`, `marketing-screenshots`, `polar-checkout`, `backend-judgement`, `systematic-reasoning`, `photo-cull`, `ponytail`, plus reference patterns for Swift/SwiftUI, Python, Postgres, migrations and API design.

## Undo

- Replaced files are in `~/.claude/backups/pre-install-<timestamp>/`. The path prints at the end.
- Everything is a symlink: `rm ~/.claude/skills/<name>` removes one and leaves the repo alone.
- The audit archives to `~/.claude/archive/` and never deletes.
