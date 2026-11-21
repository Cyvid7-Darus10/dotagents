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

Reference point from real usage: interactive sessions on the old setup started at a **median of 77,406 tokens** (11 sessions, range 70.9k–77.6k, from local transcripts). Interactive sessions wait for connectors, so they carry the full connector cost that headless runs only partly show. Connectors explain only about 12k of the roughly 40k gap to headless runs; the rest is not yet attributed (interactive-only prompt sections, session-start hooks and other always-on context are candidates).

## What this means

1. **Claude Code itself costs about 35k.** That is the floor: system prompt plus built-in tools. You can't configure it away.
2. **Connectors are the biggest lever.** Each one adds its tool names and instructions to every session, whether or not you use it. Disconnect the ones you don't use on claude.ai, which removes them everywhere. Per-project `/mcp` toggles only cover the folders you set them in.
3. **Always-on injections are the second lever.** The i-have-adhd flag adds about 2.5k per session. It's worth it if the output format helps you, but it's a cost you should choose on purpose. The installer leaves it off unless you pass `--adhd`.
4. **Plugin skills looked cheap (about 18 tokens each), but that is an artifact.** The skill listing has a budget of about 1% of the window. This setup was already over it, so Claude Code was cutting descriptions, and removing skills mostly restored the ones that had been cut instead of lowering the count. Judge skills by whether the listing fits, not by startup tokens.
5. **Trimming skills, agents and rules measured only 251 tokens here,** for the same reason. The real gain is a listing that fits, so the agent can see every description and pick the right skill, plus no reflexive subagent spawning from "MUST BE USED" wording.
6. **Startup tokens are not the whole bill.** After the first turn, the startup context is a prompt-cache read at about a tenth of the input price. Tool output and conversation growth drive most spend, so keep large outputs out of the window (see [CONTEXT.md](CONTEXT.md)).

## Second machine: a full audit after a plain install (2026-11-22)

A setup that had run `install.sh` without the audit, then ran the audit end to end. Headless `claude -p`, Opus, `--reps 2`, same folder before and after.

| Condition | Before | After | Change |
|---|---|---|---|
| Current setup (median) | 55,030 | 47,457 | −7,573 (−14%) |
| claude.ai connectors off | 48,068 | 42,829 | **−5,239 (−11%)** |

Read the connectors-off row: it is stable between runs. The current-setup row varied by about 9k between runs in the first experiment, so with 2 reps its −7.6k is indicative only. Many changes were made at once, so this measures the whole audit, not any one change.

What was changed: three plugins with 0 uses in 236 days of transcripts turned off (28 skills, 7 servers that were never signed in), 10 local MCP servers removed (unused, failing, or duplicates of a claude.ai connector), 4 overlapping skills and 2 agents archived, and a 17.7 KB memory index cut to 8.3 KB with every link kept. Connectors were left to the owner to disconnect on claude.ai, so about 4.6k of connector cost remains.

Lessons that went back into the tooling: `install.sh` alone adds and never removes, so it now says so and points to the audit. `inventory.py` now reports ranked findings, connection status (`--live`), duplicate endpoints and skill-listing overflow, and no longer counts reference copies of skills or misses symlinked rules.

## Removed: the token-saving hooks (2026-11-22)

Earlier versions shipped opt-in `--hooks` (`pre-read.mjs`, `compress.mjs`). A code review found they could not save tokens. `compress.mjs` returned `additionalContext`, which adds a summary next to the full tool output instead of replacing it, and for Bash it threw on the object response and returned nothing. `pre-read.mjs` blocked a repeat read of the same file and range for the whole session, even after an edit or a compaction had removed the original from context, which forced extra turns. The "316k tokens/week" figure had no method behind it. Both hooks were removed. If you installed them, delete their entries from `~/.claude/settings.json`.

## Not yet measured

- Interactive-session startup after the cleanup. Run `/context` after restarting, or wait for transcripts. `setup-audit` Phase 6 does this.
- Whether `personal_docs/` reduces exploration tokens on repeat sessions in the same project. This is plausible (the agent reads a 60-line index instead of rediscovering the repo) but unproven. We'd need paired tasks with and without it.
- Output-token effects of i-have-adhd and of a "be concise" rule, which work against the 2.5k input cost.
