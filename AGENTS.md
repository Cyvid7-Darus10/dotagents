# You are inside an agent-setup repo

This repo is a portable setup for coding agents: global instructions, skills, a `personal_docs/` convention, and an auditor that cleans up an existing setup.

## On session start: audit mode

If the user opened this repo without asking for something specific, or asks to "set up", "install", "audit" or "clean up", **run the setup audit**:

1. Read `skills/setup-audit/SKILL.md` and follow its phases in order.
2. Work **with** the user. Explain their current setup and its measured cost in plain language, ask how they work, then propose a tailored plan with why / effect / undo for each change.
3. Phases 0–4 are read-only. Change nothing until the user approves the plan. Running `measure.py` costs API usage, so ask first.
4. Installing goes through `./install.sh --dry-run` first, then `./install.sh` with the options they chose.

If the user asks for something else (editing this repo, a question), do that instead, and mention in one line that `setup-audit` is available.

## Working on this repo

- It is **public**. No personal data, app names, account IDs, emails or paths under a real home directory.
- Lean beats complete. Every skill, agent and rule installed from here costs context in every user session. Add something only if it changes outcomes, and say when to use it in `docs/TOOLKIT.md`.
- `global/AGENTS.md` is the agent-neutral source of truth and stays under ~120 lines. Claude-only extras go in `global/CLAUDE.md`.
- Language rules live in `rules/<lang>/` with `paths:` frontmatter, so they load only for matching files.
- Skills: one folder each, `SKILL.md` with `name` + a `description` that says when to use it. Scripts stdlib-only, read-only unless the skill says otherwise.
- After changing `install.sh` or `skills/setup-audit/scripts/`, run `./install.sh --dry-run` and `python3 -I skills/setup-audit/scripts/inventory.py`, and check that both succeed.
- Conventional commits. No AI attribution lines.
