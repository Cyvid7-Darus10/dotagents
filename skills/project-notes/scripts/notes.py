#!/usr/bin/env python3
"""Helper for personal_docs/, the private per-project notes every agent shares.

  notes.py brief [--cwd DIR]  Print README.md plus the active work/ items. Prints
                              nothing if there is no personal_docs/ (safe as a hook).
  notes.py init  [--cwd DIR]  Create personal_docs/ with README.md and work/ at the
                              project root. Other files are created on first entry.
  notes.py check [--cwd DIR]  Lint: git-ignored, size budgets, stale entries,
                              dead path references, likely secrets. Exit 1 on problems.

Stdlib only. Never edits anything except `init` creating files that don't exist.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

FOLDER = "personal_docs"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
README_MAX_LINES = 60
TOPIC_MAX_LINES = 250
STALE_DAYS = 90
BRIEF_MAX_LINES = 80
TOPIC_FILES = ("architecture.md", "runbook.md", "gotchas.md", "decisions.md", "learnings.md")
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:(password|secret|token|api_key)\s*[:=]\s*['\"]?[^\s'\"<>]{8,}))"
)
VERIFIED = re.compile(r"Verified:\**\s*(\d{4}-\d{2}-\d{2})")
PATH_REF = re.compile(r"`([\w.\-]+(?:/[\w.\-]+)+\.\w+)(?::\d+)?`")


def git_root(start: Path) -> Path | None:
    out = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    return Path(out.stdout.strip()) if out.returncode == 0 else None


def find_notes(cwd: Path) -> Path | None:
    """Nearest personal_docs/ from cwd upward, stopping at the git root or $HOME."""
    stop = git_root(cwd) or Path.home()
    for d in (cwd, *cwd.parents):
        if (d / FOLDER).is_dir():
            return d / FOLDER
        if d == stop or d == Path.home():
            return None
    return None


def work_items(notes: Path) -> list[tuple[str, str]]:
    items = []
    for f in sorted((notes / "work").glob("*.md")):
        if f.name.startswith("_"):
            continue
        text = f.read_text(errors="replace")
        nxt = re.search(r"\*\*Next:\*\*\s*(.+)", text)
        items.append((f.name, nxt.group(1).strip() if nxt else "(no Next line)"))
    return items


def cmd_brief(cwd: Path) -> int:
    notes = find_notes(cwd)
    if notes is None:
        return 0
    readme = notes / "README.md"
    print(f"Project notes: {notes} (private, git-ignored). Read before changing anything; "
          f"open other files only when the task needs them. Write back what you learn.\n")
    if readme.exists():
        lines = readme.read_text(errors="replace").splitlines()
        print("\n".join(lines[:BRIEF_MAX_LINES]))
        if len(lines) > BRIEF_MAX_LINES:
            print(f"\n[README truncated at {BRIEF_MAX_LINES} lines; trim it to {README_MAX_LINES}]")
    items = work_items(notes)
    if items:
        print("\nActive work (personal_docs/work/):")
        for name, nxt in items:
            print(f"- {name}: next → {nxt}")
    return 0


def is_ignored(path: Path) -> bool | None:
    out = subprocess.run(["git", "-C", str(path.parent), "check-ignore", "-q", path.name], capture_output=True)
    return {0: True, 1: False}.get(out.returncode)  # 128 = not a git repo


def cmd_init(cwd: Path) -> int:
    existing = find_notes(cwd)
    if existing:
        print(f"already exists: {existing}")
        return 0
    notes = (git_root(cwd) or cwd) / FOLDER
    (notes / "work").mkdir(parents=True, exist_ok=True)
    created = []
    for rel in ("README.md", "work/_template.md"):
        dest = notes / rel
        if not dest.exists():
            shutil.copyfile(TEMPLATES / rel, dest)
            created.append(rel)
    print(f"created {notes}: {', '.join(created)}")
    if is_ignored(notes) is False:
        print("WARNING: personal_docs/ is NOT git-ignored here. Add it to your global excludes file:\n"
              "  echo 'personal_docs/' >> \"$(git config --global core.excludesFile || echo ~/.config/git/ignore)\"")
    return 0


def check_file(f: Path, root: Path, today: dt.date) -> list[str]:
    problems = []
    rel = f.relative_to(root.parent)
    raw = f.read_text(errors="replace")
    lines = raw.splitlines()
    text = re.sub(r"<!--.*?-->", lambda m: "\n" * m.group(0).count("\n"), raw, flags=re.S)  # template examples live in comments
    limit = README_MAX_LINES if f.name == "README.md" and f.parent == root else TOPIC_MAX_LINES
    if f.parent == root and len(lines) > limit:
        problems.append(f"{rel}: {len(lines)} lines (budget {limit}); roll old entries into docs/ or archive/")
    for i, line in enumerate(text.splitlines(), 1):
        if SECRET.search(line):
            problems.append(f"{rel}:{i}: looks like a secret; store the variable name, not the value")
    for m in VERIFIED.finditer(text):
        age = (today - dt.date.fromisoformat(m.group(1))).days
        if age > STALE_DAYS:
            problems.append(f"{rel}: entry verified {m.group(1)} ({age} days ago); re-check or delete it")
    for m in PATH_REF.finditer(text):
        if not (root.parent / m.group(1)).exists() and not (root / m.group(1)).exists():
            problems.append(f"{rel}: references `{m.group(1)}`, which no longer exists")
    return problems


def cmd_check(cwd: Path) -> int:
    notes = find_notes(cwd)
    if notes is None:
        print("no personal_docs/ found (run: notes.py init)")
        return 1
    problems = []
    if is_ignored(notes) is False:
        problems.append(f"{notes}: NOT git-ignored; add personal_docs/ to the global excludes file")
    if not (notes / "README.md").exists():
        problems.append("README.md missing; every agent reads it first")
    today = dt.date.today()
    for f in sorted(notes.rglob("*.md")):
        if "archive" not in f.relative_to(notes).parts:
            problems += check_file(f, notes, today)
    for p in problems:
        print(p)
    print(f"{notes}: {'ok' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("brief", "init", "check"))
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()
    cwd = Path(args.cwd).expanduser().resolve()
    return {"brief": cmd_brief, "init": cmd_init, "check": cmd_check}[args.command](cwd)


if __name__ == "__main__":
    sys.exit(main())
