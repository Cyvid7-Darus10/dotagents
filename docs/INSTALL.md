# Install

`install.sh` symlinks this repo into your agents' config folders, so edits in the repo go live. It backs up anything it replaces.

Installing and cleaning up are two steps:

1. **Install** adds and links files. In a terminal it asks two questions (context7 + i-have-adhd on demand, and ADHD mode in every session), then prints what is on and off.
2. **Clean up** with the [audit](AUDIT.md). The installer removes nothing, so unused MCP servers, plugins and skills stay until the audit runs. At the end the installer offers to start it; it changes nothing until you approve its plan.

```bash
./install.sh --dry-run                 # preview every change
./install.sh                           # install, answer the questions, then optionally audit
./install.sh --status                  # what is on, what is off, and how to turn it on
./install.sh --skills humanizer,verify-app,project-notes,setup-audit   # pick skills
```

One-line install with default options, without cloning first (clones to `~/.local/share/dot-agent`):

```bash
curl -fsSL https://raw.githubusercontent.com/cyruspastelero/dot-agent/main/setup.sh | bash
```

## Flags

By default it links all 24 skills (workflow skills and all commands are manual: start them with `/name`, so they stay out of the skill listing) and adds the `personal_docs` startup hook, capped at about 5,000 characters. Plugins and MCP servers are opt-in.

| Flag | Effect |
|---|---|
| `--skills a,b,c` | Link only these skills (default: all) |
| `--status` | Show what is on and off. Changes nothing |
| `--adhd` / `--no-adhd` | Install, enable and turn on i-have-adhd for every session (~2.5k tokens per session), or skip the question |
| `--no-notes-hook` | Don't auto-load `personal_docs/` when a Claude Code session starts |
| `--plugins` / `--no-plugins` | Install (or re-enable) the i-have-adhd plugin, run via `/i-have-adhd`, and the context7 MCP server, pinned. Or skip the question |
| `--no-prompt` | Ask nothing; take the defaults (no opt-ins, no audit). Also the behavior when there is no terminal |
| `--sounds` | macOS notification sounds |

## What gets linked

| Agent | Where |
|---|---|
| Claude Code | `~/.claude/{CLAUDE.md, AGENTS.md, skills, agents, commands, rules}` |
| Codex | `~/.codex/AGENTS.md` (and `~/.agents/skills/` if it exists) |
| Gemini CLI | `~/.gemini/GEMINI.md` |
| Cursor | Paste `global/AGENTS.md` into *Rules for AI* (Cursor has no global file) |

It also adds `personal_docs/` to your global git excludes, and merges `settings.json` without overwriting your values (a copy goes to the backup first): `cleanupPeriodDays`, a permission deny list, and the `personal_docs` startup hook.

The deny list blocks reading or editing `~/.ssh` and `~/.aws`, reading credential and `.env` files, and these commands: `curl` or `wget` that send data (`-d`, `--data`, `-F`, `--post-data`), piping a download into a shell, `rm -rf` on `/` or `~`, `git remote add`, `npm publish`, `nc`. If your agent posts to APIs with `curl`, remove those entries from `~/.claude/settings.json`.

Rule files in `~/.claude/rules/common/` from older versions are folded into `global/AGENTS.md`. Known ones go to the backup. Rules you wrote yourself move up to `~/.claude/rules/`, so they keep loading.

## What's inside

```
dot-agent/
├── AGENTS.md          instructions for agents opened in this repo (audit mode)
├── global/            AGENTS.md for every agent; CLAUDE.md imports it + Claude extras
├── skills/            24 skills; setup-audit and project-notes are the core
├── agents/ commands/  reviewers, tdd-guide, build fixer; /tdd /verify /ponytail …
├── rules/<lang>/      path-scoped, load only for matching files
└── docs/              these guides
```

The other skills: `humanizer`, `verify-app`, `audit-app-design`, `shipping-ios-apps`, `appstore-release`, `marketing-screenshots`, `polar-checkout`, `backend-judgement`, `systematic-reasoning`, `photo-cull`, `ponytail`, plus reference patterns for Swift/SwiftUI, Python, Postgres, migrations and API design.

## Undo

- Replaced files are in `~/.claude/backups/pre-install-<timestamp>/`. The path prints at the end.
- Linked files are symlinks: `rm ~/.claude/skills/<name>` removes one and leaves the repo alone.
- Settings: restore `settings.json` from the backup. If you used `--plugins`: `claude plugin uninstall i-have-adhd@i-have-adhd` and `claude mcp remove context7`.
- The audit archives to `~/.claude/archive/` and never deletes.
