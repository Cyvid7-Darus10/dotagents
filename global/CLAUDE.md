@AGENTS.md

## Claude Code specifics

- Subagents: use them for independent parallel work or broad searches whose file dumps I don't need. Do single lookups yourself.
- Plan mode for changes that span several files or have open design questions. Skip it for small edits.
- Skills load on demand. Invoke one when its description matches the task; don't pre-load "just in case".
- MCP tools are deferred. Load only the ones the task needs, in one ToolSearch call.
- Auto-memory: save who I am, my corrections, and project facts the repo doesn't record. Never save what git or the code already says.
- `/context` shows what is eating the window; `/doctor` flags unused skills and servers.
