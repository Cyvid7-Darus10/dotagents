# personal_docs

Each project gets a private, git-ignored notebook that all your agents share. They read it first, resume unfinished work from it, and write back what they learn. The `project-notes` skill holds the full convention, templates and `notes.py`.

```
your-project/
└── personal_docs/      git-ignored via your global excludes, never committed
    ├── README.md       read every session, ≤60 lines: focus + a "read when" map
    ├── work/           one file per unfinished task: plan, state, next step
    ├── runbook.md      ┐
    ├── gotchas.md      │ opened only when the task needs them,
    ├── decisions.md    │ created on first entry,
    ├── architecture.md │ each entry has a source and a "Verified:" date
    ├── learnings.md    ┘
    ├── docs/           longer reference
    └── archive/        finished work, retired entries
```

| Choice | Why |
|---|---|
| Only `README.md` is read every session | A session pays for about 60 lines, not the whole folder |
| A **Next** line per task in `work/` | Any agent can pick up cold, even a different tool than yesterday |
| Source + `Verified:` date per entry | Notes go stale. Old entries get re-checked, not trusted |
| Created lazily, with size budgets | Empty or bloated notes get ignored |
| Loaded automatically in Claude Code | A SessionStart hook runs `notes.py brief`, which prints nothing where there are no notes |

`notes.py check` lints a project's notes. It confirms they're git-ignored and flags entries older than 90 days, paths that no longer exist, files over budget, and anything that looks like a secret.

**Why not `CLAUDE.md`?** It's committed, team-facing, and read by one agent. `personal_docs/` is private and shared by every agent you use.

**Why not agent memory?** Memory is per tool and per user, so it suits how you like to work. Project facts belong with the project.
