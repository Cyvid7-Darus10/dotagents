#!/usr/bin/env python3
"""Show what this setup has turned on, what is off, and how to turn each part on.

Read-only. Usage: status.py REPO [CLAUDE_DIR]
Run it any time with ./install.sh --status.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ADHD_PLUGIN = "i-have-adhd@i-have-adhd"


@dataclass(frozen=True)
class Row:
    name: str
    state: str  # on | partial | off | disabled | not run
    detail: str
    fix: str = ""


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as err:
        print(f"warning: could not read {path}: {err}", file=sys.stderr)
        return {}


def points_into(link: Path, target: Path) -> bool:
    return link.is_symlink() and link.resolve() == target.resolve()


def linked_row(name: str, sources: list[Path], dest_dir: Path, fix: str) -> Row:
    linked = sum(points_into(dest_dir / s.name, s) for s in sources)
    state = "on" if sources and linked == len(sources) else "partial" if linked else "off"
    return Row(name, state, f"{linked} of {len(sources)} linked", "" if state == "on" else fix)


def adhd_row(claude_dir: Path, settings: dict) -> Row:
    installed = ADHD_PLUGIN in read_json(claude_dir / "plugins" / "installed_plugins.json").get("plugins", {})
    enabled = settings.get("enabledPlugins", {}).get(ADHD_PLUGIN, True)
    always = (claude_dir / ".i-have-adhd-always").exists()
    if not installed:
        return Row("ADHD mode", "off", "plugin not installed", "./install.sh --adhd")
    if not enabled:
        return Row("ADHD mode", "disabled", "installed but switched off", "./install.sh --adhd")
    if always:
        return Row("ADHD mode", "on", "every session (~2.5k tokens)")
    return Row("ADHD mode", "partial", "on demand: type /i-have-adhd", "./install.sh --adhd for every session")


def audit_row(claude_dir: Path, repo: Path) -> Row:
    runs = sorted(p.name for p in (claude_dir / "backups").glob("pre-audit-*"))
    fix = f"cd \"{repo}\" && claude \"Audit my setup.\""
    if not runs:
        return Row("Cleanup audit", "not run", "unused MCP servers, plugins and skills are still there", fix)
    stamp = runs[-1].removeprefix("pre-audit-")
    return Row("Cleanup audit", "on", f"last run {stamp[:4]}-{stamp[4:6]}-{stamp[6:8]}")


def collect(repo: Path, claude_dir: Path, claude_json: Path) -> list[Row]:
    settings = read_json(claude_dir / "settings.json")
    commands = [h.get("command", "") for groups in settings.get("hooks", {}).values()
                for group in groups for h in group.get("hooks", [])]
    notes_on = any("notes.py" in c and c.rstrip().endswith("brief") for c in commands)
    template_deny = set(read_json(repo / "settings.json").get("permissions", {}).get("deny", []))
    deny = template_deny & set(settings.get("permissions", {}).get("deny", []))
    servers = read_json(claude_json).get("mcpServers", {})
    reinstall = "./install.sh"
    rows = [
        linked_row("Instructions", [repo / "global" / "AGENTS.md"], claude_dir, reinstall),
        linked_row("Skills", sorted(p for p in (repo / "skills").iterdir() if p.is_dir()), claude_dir / "skills", reinstall),
        linked_row("Agents", sorted((repo / "agents").glob("*.md")), claude_dir / "agents", reinstall),
        linked_row("Commands", sorted((repo / "commands").glob("*.md")), claude_dir / "commands", reinstall),
        Row("personal_docs hook", "on" if notes_on else "off", "loads project notes at start",
            "" if notes_on else reinstall),
        Row("Safety deny list", "on" if deny == template_deny else "partial" if deny else "off",
            f"{len(deny)} of {len(template_deny)} rules", "" if deny == template_deny else reinstall),
        adhd_row(claude_dir, settings),
        Row("context7 docs MCP", "on" if "context7" in servers else "off", "library docs lookup",
            "" if "context7" in servers else "./install.sh --plugins"),
        audit_row(claude_dir, repo),
    ]
    return rows


def render(rows: list[Row]) -> str:
    icon = {"on": "✔", "partial": "◐", "off": "✘", "disabled": "✘", "not run": "!"}
    width = max(len(r.name) for r in rows)
    lines = []
    for r in rows:
        line = f"  {icon.get(r.state, '?')} {r.name.ljust(width)}  {r.state:<8}  {r.detail}"
        lines.append(line + (f"\n      → {r.fix}" if r.fix else ""))
    lines.append("\n  claude.ai connectors are managed at claude.ai → Settings → Connectors; /mcp shows them all.")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    repo = Path(argv[1])
    claude_dir = Path(argv[2]) if len(argv) > 2 else Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    claude_json = claude_dir / ".claude.json" if "CLAUDE_CONFIG_DIR" in os.environ else Path.home() / ".claude.json"
    print("Setup status\n")
    print(render(collect(repo, claude_dir, claude_json)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
