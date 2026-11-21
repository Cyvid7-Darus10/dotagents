# Experiments: what actually costs startup context

We measured what this setup changes instead of assuming it. Short version: on the machine we tested, **claude.ai connectors and always-on injections were what moved the number**. Trimming skills, agents and rules barely did. Every figure below is measured. Anything estimated is labeled.

## Method

- **What we measure:** the tokens in the first API request of a session, before you type anything: `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` from `claude -p "Reply with just OK." --output-format json`.
- **Environment:** Claude Code 2.1.330, Opus 5.5, macOS, run from a parent folder holding about 35 project repos, 2026-11-21.
- **One variable at a time.** Connectors toggled with `ENABLE_CLAUDEAI_MCP_SERVERS=false`. Plugins toggled with `--settings '{"enabledPlugins":{…:false}}'`. Config files swapped in place from backups for a single run, then restored by a `trap`.
- **Reproduce it:** `python3 skills/setup-audit/scripts/measure.py --cwd <folder> --reps 3`.

### Two pitfalls we hit (and fixed)

1. **Piped stdin leaks into the prompt.** Running `claude -p` inside a `bash <<EOF` heredoc let it read the rest of the script as input, adding about 500 tokens. `measure.py` now passes `stdin=DEVNULL`.
2. **Headless mode doesn't wait for every connector.** The same config gave 41.3k, 43.3k and 50.6k across runs, depending on how many connectors had connected before the first request. Connector numbers from headless runs are a lower bound. The connector-off baseline was stable to within 16 tokens.

## Results

| # | Condition | Runs | Startup tokens | Δ vs baseline |
|---|---|---|---|---|
| B | **Baseline:** current setup, connectors off | 4 | 37,867 – 37,883 | — |
| 1 | + claude.ai connectors on (15 connectors, 6 disabled per project) | 3 | 41,320 / 43,318 / 50,640 | **+3.4k to +12.8k** |
| 2 | Same, from a fresh folder with no per-project disables | 1 | 49,929 | +12.0k |
| 3 | i-have-adhd always-on flag removed | 1 | 35,408 | **−2.5k** |
| 4 | Vercel plugin (49 skills) disabled | 1 | 37,022 | −0.9k |
| 5 | Old config files (45 skills, 17 agents, 8.7 KB always-on rules, no global AGENTS.md) | 2 | 38,118 | **+0.25k** |

Reference point from real usage: interactive sessions on the old setup started at a **median of 77,406 tokens** (11 sessions, range 70.9k–77.6k, from local transcripts). Interactive sessions wait for connectors, so they carry the full connector cost that headless runs only partly show.

## What this means

1. **Claude Code itself costs about 35k.** That is the floor: system prompt plus built-in tools. You can't configure it away.
2. **Connectors are the biggest lever.** Each one adds its tool names and instructions to every session, whether or not you use it. Disconnect the ones you don't use on claude.ai, which removes them everywhere. Per-project `/mcp` toggles only cover the folders you set them in.
3. **Always-on injections are the second lever.** The i-have-adhd flag adds about 2.5k per session. It's worth it if the output format helps you, but it's a cost you should choose on purpose. The installer leaves it off unless you pass `--adhd`.
4. **Framework plugins cost about 18 tokens per skill** (Vercel: 0.9k for 49 skills). Enable them only in the projects that use them.
5. **Trimming skills, agents and rules saves little at startup:** 251 tokens here, because descriptions are short and language rules were already path-scoped. Do it for other reasons: fewer wrong auto-picks, no reflexive subagent spawning from "MUST BE USED" wording, and one source of truth across agents.

## Not yet measured

- Interactive-session startup after the cleanup. Run `/context` after restarting, or wait for transcripts. `setup-audit` Phase 6 does this.
- Whether `personal_docs/` reduces exploration tokens on repeat sessions in the same project. This is plausible (the agent reads a 60-line index instead of rediscovering the repo) but unproven. We'd need paired tasks with and without it.
- Output-token effects of i-have-adhd and of a "be concise" rule, which work against the 2.5k input cost.
