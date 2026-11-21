---
name: project-notes
description: Create, read and maintain the private per-project knowledge base in `personal_docs/` (architecture, runbook, gotchas, decisions, learnings, dated session notes). Use when starting work in a folder that has no personal_docs yet, when you learn something non-obvious worth keeping, when asked to "write this down", "take notes", "remember this for the project", or to write a handoff at the end of a substantial session.
---

# project-notes

`personal_docs/` is a private, git-ignored folder at the root of a project (or any working folder). It holds what agents and the user learn about that project, so the next session, in any agent, starts informed. It is agent-neutral plain markdown. Claude, Codex, Gemini and Cursor all read and write it the same way.

## Where it lives

- The nearest `personal_docs/` going up from the working directory, stopping at the git root (or `$HOME`).
- No git repo: the working folder itself.
- It must be git-ignored. Check with `git check-ignore -q personal_docs/ && echo ignored`. If it is not ignored, add `personal_docs/` to the global excludes file (`git config --global core.excludesFile`, default `~/.config/git/ignore`), not to the repo's `.gitignore`. Tell the user you did.

## Layout

```
personal_docs/
├── README.md        index + current focus. Read this first, always. Keep under ~60 lines
├── architecture.md  components, data flow, key files, external services
├── runbook.md       run/test/build/deploy commands; env var NAMES and where values live
├── gotchas.md       symptom → cause → fix, newest first
├── decisions.md     dated decisions: why, what was rejected, when to revisit
├── learnings.md     lessons beyond one bug: preferences, patterns, process
├── notes/           YYYY-MM-DD-topic.md session notes and handoffs
└── docs/            longer reference: specs, research, API notes
```

Templates are in `templates/` next to this file.

## Init (folder has no personal_docs)

1. Copy `templates/` to `<root>/personal_docs/`. Skip `notes/_template.md` (keep it only as a reference).
2. Fill `README.md`, `architecture.md` and `runbook.md` from what you can verify: manifests, scripts, CI config, README, entry points. Leave unknowns as `<unknown>` rather than guessing.
3. Seed `gotchas.md` and `decisions.md` only with things you actually found, such as TODO/FIXME clusters or comments explaining odd code. Don't invent entries.
4. Confirm git ignores it. Tell the user in one line what you created.

## Read (every session)

- Read `personal_docs/README.md` before the first change. Open other files only when the task touches them. Read `gotchas.md` before debugging and `runbook.md` before running things.
- Treat it as the user's notes: likely right, but verify a fact against the code before acting on it. If a note is stale, fix it.

## Write back (when it earns a line)

Write when you learn something a future agent could not get cheaply from the code or git history:

| You learned | Goes in |
|---|---|
| A trap that cost time (wrong env, flaky step, misleading error) | `gotchas.md` |
| A choice between options, with the reason | `decisions.md` |
| How to run, test, deploy or release, or a new env var | `runbook.md` |
| A structural fact (new service, data flow, key file) | `architecture.md` |
| A preference or pattern for working here | `learnings.md` |

Rules:
- Date every entry (`YYYY-MM-DD`, absolute, never "yesterday"). Newest first.
- Edit or delete wrong or stale entries; don't pile contradictions on top.
- No secrets, tokens or personal data. Env var names only, with where the value lives.
- Don't copy code or restate the git log. Link paths and commits instead.
- Update `README.md`'s "Current focus" and "Last updated" when the focus changes.

## Handoff (end of substantial work, or when asked)

Write `notes/YYYY-MM-DD-<topic>.md` using `templates/notes/_template.md` (Goal / Done / State / Next). Link it from README "Current focus". One file per session topic. Append to today's file if it exists.

## Relation to other memory

- Agent-level memory (Claude auto-memory, Codex memories) is for who the user is and how they like to work, across all projects.
- `personal_docs/` is for this project. Project facts go here, so every agent sees them.
- Committed docs (`README`, `CLAUDE.md`/`AGENTS.md` in the repo) are for the team. Promote a note there only when the user asks.
