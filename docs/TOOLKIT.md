# Toolkit: what to install, and when to reach for it

Every plugin, skill and MCP server costs context in **every** session, even when idle (names, descriptions, hook output). So the rule is: install only what changes outcomes for the work you actually do, and scope project-specific tools to the project.

Star counts and activity were checked on 2026-11-21. Savings figures are the projects' own claims unless noted.

## Default set (installed by `./install.sh --plugins`)

| Tool | What it does | Use when | Skip when |
|---|---|---|---|
| [i-have-adhd](https://github.com/ayghri/i-have-adhd) (62k★, MIT) | Reshapes replies: action first, numbered steps, no preamble, ≤5-item lists | You want scannable, action-first replies. Installed on demand (`/i-have-adhd`); `install.sh --adhd` turns it on for every session | It costs ~2.5k input tokens per session (measured, see EXPERIMENTS.md). Keep it on demand unless the format clearly helps you |
| [context7](https://github.com/upstash/context7) (65k★, MIT) | Pulls current, version-specific library docs on demand | Any library/framework/CLI question where versions matter | Stable libs with good types, and the LSP already answers it |
| LSP plugins (`swift-lsp`, `typescript-lsp`, … from `claude-plugins-official`) | Real go-to-definition, references and diagnostics | Typed codebases in that language | Languages you don't write |
| [ponytail](../skills/ponytail/SKILL.md) (bundled) | "Lazy senior dev": simplest working change, YAGNI | Agent over-engineers; `/ponytail-review` before merging | Greenfield design work where options matter |

## On demand (install per project or when the situation arises)

| Tool | What it does | Use when | Skip when / cost |
|---|---|---|---|
| [graphify](https://github.com/safishamsi/graphify) (151k★, Apache-2.0) | Builds a knowledge graph of a repo (`graphify-out/`); agent queries it instead of grepping | Large or unfamiliar repo, cross-module tracing, onboarding, PR impact | Small apps you know well. `graphify claude install` adds CLAUDE.md rules + a PreToolUse hook, so run it **per project**, never globally. Code is parsed locally; docs/PDFs/images go to your model provider |
| [serena](https://github.com/oraios/serena) (32k★) | MCP server with semantic, symbol-level retrieval and editing | Big multi-language codebases where most tokens go to reading files | An LSP plugin already covers your language. It adds many tools |
| [caveman](https://github.com/JuliusBrussee/caveman) (122k★, Apache-2.0) | Terse "caveman" voice (output), plus 4.x proxy/input compression and model routing | Long sessions where reply length dominates: use `/ultracave` (reported ~35% fewer output tokens than a plain "be concise" baseline) | As an always-on default. Its own benchmark shows `/caveman` only ~3% shorter than "be concise" (which `global/AGENTS.md` already says). The plugin auto-starts every session, rules cost ~1.2k tokens, and 4.x installs a proxy. Skill only: `npx skills add JuliusBrussee/caveman -g`, then `/caveman` |
| [superpowers](https://github.com/obra/superpowers) (323k★, MIT) | Full methodology: brainstorm → plan → subagent-driven TDD | You want an enforced process on a big feature | You already use plan mode + `/tdd`; it adds many skills to every session |
| [context-mode](https://github.com/mksglu/context-mode) (34k★) | Keeps large tool output in a local sandbox/FTS index instead of the window | Sessions dominated by huge logs/JSON/test output | The bundled `hooks/compress.mjs` already trims tool output |
| [claude-mem](https://github.com/thedotmack/claude-mem) (119k★, Apache-2.0) | Captures and re-injects compressed session history | Agents without built-in memory | Claude Code: built-in auto-memory covers it, and claude-mem adds context every session |

## Bundled skills (this repo)

| Skill | Reach for it when |
|---|---|
| `setup-audit` | Agent setup feels slow or bloated, after cloning this repo, or every few months |
| `humanizer` | Any copy a person will read: UI strings, README, release notes, store listing |
| `verify-app` | "Test everything properly", or after a port/migration |
| `audit-app-design` | UI feels off or templated; pre-release design pass |
| `shipping-ios-apps` / `appstore-release` / `marketing-screenshots` | Taking an iOS app from idea to App Store, cutting a release, store screenshots |
| `polar-checkout` | Selling subscriptions on the web with Polar.sh |
| `backend-judgement` | Writing or reviewing handlers, queries, jobs, auth |
| `systematic-reasoning` | Non-trivial, ambiguous or cross-system change, before proposing a fix |
| `photo-cull` | Picking keepers from a folder of RAW photos |
| `api-design`, `database-migrations`, `postgres-patterns`, `python-*`, `swift-*`, `swiftui-patterns` | Reference patterns, loaded only when the task matches |

Design skills that pair well (third-party, install separately): `impeccable`, `design-taste-frontend`, `emil-design-eng`, and the `better-*` family.

## MCP servers and claude.ai connectors

- **User scope:** only what you use across most projects (context7, plus your payments or docs server).
- **Project scope:** a service one repo talks to (Supabase, Sentry, Vercel) goes in that repo's `.mcp.json`, or stays a claude.ai connector you turn off elsewhere.
- **claude.ai connectors** come along automatically. To turn one off, use `/mcp` (per project) or disconnect it on claude.ai (everywhere). `disableClaudeAiConnectors: true` turns them all off.
- **Duplicates:** if a plugin bundles an MCP server you already have as a connector, disable one (`/mcp`).
- **Never-authenticated servers** are pure overhead. Sign in or disable.
