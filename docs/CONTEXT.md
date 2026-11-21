# Context budget playbook

The context window is shared by everything loaded before you type: system prompt, tool names, skill descriptions, instructions, memory. The more that is there at startup, the less room the work gets, the sooner auto-compact fires, and the worse instructions are followed.

## Measure first

1. `/context` in Claude Code: a breakdown of what is loaded.
2. `/doctor`: flags unused skills, servers and plugins.
3. `python3 skills/setup-audit/scripts/inventory.py`: everything installed, with sizes and how often transcripts show it used.

A real example from the setup this repo was built on: interactive sessions started at a median of **77k tokens** before the first prompt. Claude Code's own floor is ~35k. Most of the rest came from 15 claude.ai connectors. See [EXPERIMENTS.md](EXPERIMENTS.md) for the measured breakdown.

## Levers, biggest first (measured order: connectors ≫ always-on injections > plugin skill packs > skills/rules)

1. **MCP servers and connectors.** Tool schemas are deferred, but every server still costs its tool names and instructions. Disable unused and never-authenticated servers, and remove duplicates (a plugin's bundled server plus the same claude.ai connector). Scope single-project services to that project.
2. **Plugins that bundle many skills.** One framework plugin can add 40+ skill descriptions. Enable it in the projects that need it (`enabledPlugins` in the project's `.claude/settings.json`), not globally.
3. **Skills.** Archive ones you never invoke. For skills you only run by hand, set `disable-model-invocation: true` in the frontmatter or `"skillOverrides": {"name": "user-invocable-only"}`. Their description then leaves the model's listing.
4. **Always-on instructions.** `CLAUDE.md`/`AGENTS.md` under ~150 lines. Language rules go in `rules/<lang>/` with `paths:` frontmatter so they load only for matching files.
5. **Memory index.** `MEMORY.md` is one line per memory. Content goes in the memory files.
6. **Agent descriptions.** "MUST BE USED" / "use PROACTIVELY" make the model spawn subagents for everything. Describe when the agent helps instead.
7. **Output.** A concise-voice rule in `AGENTS.md` gets most of the gain. Keep `/ultracave` for very long sessions.

## Session habits

- One task per session. `/clear` between unrelated tasks.
- `/compact <what to keep>` before the window fills, not after.
- Broad research goes to a subagent; only its conclusion comes back.
- Raise `cleanupPeriodDays` (e.g. 90) so `setup-audit` has enough history to judge what you actually use.
