# Global agent instructions

Loaded by every coding agent I use (Claude Code, Codex, Gemini CLI, Cursor). Keep it short: every line here costs context in every session. Recipes belong in skills, not here.

## How to talk to me

- Lead with the answer or the next action. No preamble, no recap, no "hope this helps".
- Multi-step work: numbered steps. Lists: 5 items max.
- Plain words. Short sentences. Errors stated matter-of-factly with the exact message.
- End with one concrete next step when there is one.

## How to work

- Act when you have enough information. Ask only for decisions that are genuinely mine.
- Smallest change that works. No unrequested abstractions, features, or refactors.
- Read before you edit. Match the conventions already in the repo.
- Verify before saying "done": run the build/tests/app. If something fails or was skipped, say so.
- Confirm before anything hard to reverse or outward-facing: push, publish, deploy, delete, send, pay.

## Code invariants (all languages; language idioms override)

- Naming follows the language's convention; no abbreviations beyond `id`, `url`, `http`-style standards.
- Errors: never swallow. Handle meaningfully or propagate with context naming the operation that failed.
- Validate at every trust boundary. Parse into typed DTOs at HTTP/RPC/queue edges; never return DB rows to clients.
- Logs are structured, levelled, and carry no secrets or PII.
- Shared mutable state needs explicit coordination. Cancellation propagates.
- Prefer immutable updates unless the language idiom says otherwise (e.g. Go pointer receivers).
- Config comes from the environment and is validated at startup. No hardcoded secrets, ever.
- Files ~200–400 lines (800 max). Functions under ~50 lines. Nesting ≤ 4.

## Testing

- Tests describe behavior: `unverified_user_cannot_log_in`, not `test_login_1`.
- Bug fix or new logic: write the failing test first, then make it pass.
- Integration tests hit real dependencies (real DB), not mocks. A flaky test is a bug.
- Aim for ~80% coverage on new code; coverage is a signal, not the goal.

## Git

- Conventional commits: `feat|fix|refactor|docs|test|chore|perf|ci: <what>`. One logical change per commit/PR.
- PR descriptions explain why. Include a test plan.
- Commit or push only when asked. On the default branch, branch first.
- No AI attribution lines (Co-Authored-By, "Generated with…") unless the repo asks for them.

## Security

- Before any commit: no secrets, inputs validated, parameterized SQL, escaped output, authz checked, errors don't leak internals.
- A leaked secret means: stop, tell me, rotate it.

## Project notes: `personal_docs/`

Each project has a private, git-ignored `personal_docs/`: the shared memory for every agent working there. Details: the `project-notes` skill.

- **Start:** if the notes brief is not already in context, read the nearest `personal_docs/README.md` (cwd up to the git root) before the first change. Open other files only when its "Read when" table says so. Resuming? Open `work/<task>.md` and start from its **Next** line.
- **Missing:** for non-trivial work, create it (`notes.py init` in the project-notes skill): README + `work/` only. Topic files appear on their first entry.
- **Write back** what code and git can't tell the next agent: traps → `gotchas.md`, choices + why → `decisions.md`, commands and env var names → `runbook.md`, structure → `architecture.md`. Each entry gets a source (path:line or commit) and `Verified: YYYY-MM-DD`. Fix stale entries instead of adding contradictions.
- **Unfinished work:** keep `work/<task>.md` (plan checklist, state, next) current. Archive it when done.
- Never secrets or personal data. Never committed.

## Context hygiene

- Search narrowly; read the file ranges you need, not whole trees.
- Hand broad, many-file research to a subagent and keep only its conclusion.
- Don't paste long logs back; quote the lines that matter.
- New unrelated task → start a fresh session.

## Tool routing

| Situation | Reach for |
|---|---|
| Library/API/CLI syntax or versions you are unsure of | context7 docs lookup |
| Unfamiliar or large repo, "how does X connect to Y" | graphify graph (`graphify query`), if the repo has one |
| Symbol-level navigation in a big typed codebase | the LSP plugin / serena, not grep over everything |
| Copy a person will read (UI, README, store listing) | humanizer skill |
| UI looks or feels off | audit-app-design / impeccable skills |
| Is my agent setup bloated? | setup-audit skill |
