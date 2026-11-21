# The setup audit

`setup-audit` is a hygiene check for your agent setup. It finds what you don't use and removes it with your approval. Open an agent in this repo to start it, or ask any agent to run the `setup-audit` skill. Full instructions for the agent: [`skills/setup-audit/SKILL.md`](../skills/setup-audit/SKILL.md).

## What it finds

- Connectors and MCP servers that are unused, failing, never signed in, or loaded twice (a claude.ai connector plus a local or plugin copy of the same endpoint)
- Plugins with no uses, and the skills they bring
- A skill list too long for Claude Code to show in full. Past the budget, descriptions get cut and the agent can't tell when a skill fits
- Memory indexes over ~8 KB, which load every session
- Agents whose descriptions push them into every task ("MUST BE USED", "PROACTIVELY")

Usage counts come from your local transcripts. To preview the findings without changing anything:

```bash
python3 -I skills/setup-audit/scripts/inventory.py --live
```

`--live` runs `claude mcp list` from your home folder, which starts each user and plugin server once. Server addresses are shortened, so tokens in URLs never print.

## Phases

| Phase | What you see | Changes anything? |
|---|---|---|
| 1. Inventory | Everything installed, plus what you actually use. Optionally measures startup tokens (you approve the API cost, a few cents to about $1) | No |
| 2. Report | Startup cost, an inventory table, what costs the most, what's working, caveats | No |
| 3. Interview | Up to 4 questions: what you build, which agents you use, output style, borderline items | No |
| 4. Plan | Change · why · effect · undo for each row. One approval, and you can strike rows | No |
| 5. Apply | Archives (never deletes), disables, scopes to projects, installs your choices | Yes, with backups |
| 6. Verify | Measures again and shows before/after | No |

Some things only you can do, such as disconnecting a claude.ai connector. The audit lists them for you at the end.

## Results

On two setups, measured headless with `claude -p`:

- First setup: connectors added +3.4k to +12.8k tokens, i-have-adhd always-on +2.5k, and trimming skills and rules only −0.25k.
- Second setup: a full audit cut startup by 11% to 14% (−5.2k measured stably with connectors off).

Connectors and always-on injections are where the startup tokens go. Trimming skills is about a listing that fits, so the agent sees every description and picks well. Method and raw numbers: [EXPERIMENTS.md](EXPERIMENTS.md).
