#!/usr/bin/env python3
"""Read-only inventory of a Claude Code (and Codex/Gemini) setup.

Prints a markdown report of installed MCP servers, plugins, skills, agents,
commands, always-on instructions and memory, with sizes and usage counts
mined from local transcripts. It changes nothing on disk.

Usage: python3 inventory.py [--json] [--days N]
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude"
CLAUDE_JSON = HOME / ".claude.json"
PUSHY_WORDS = re.compile(r"MUST BE USED|PROACTIVELY|use immediately", re.I)
COMMAND_TAG = re.compile(r"<command-name>/?([^<]+)</command-name>")


@dataclass
class Usage:
    mcp: Counter = field(default_factory=Counter)
    skills: Counter = field(default_factory=Counter)
    agents: Counter = field(default_factory=Counter)
    sessions: int = 0
    oldest_days: float = 0.0
    baseline_tokens: list[int] = field(default_factory=list)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as err:
        print(f"warning: could not read {path}: {err}", file=sys.stderr)
        return {}


def frontmatter(path: Path) -> dict[str, str]:
    """Return top-level `key: value` pairs from a markdown file's YAML frontmatter."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return {}
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        return {}
    fields: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        top = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2)
            fields[key] = value.strip().strip(">-|").strip()
        elif key and line.startswith((" ", "\t")):
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def scan_transcripts(days: int) -> Usage:
    usage = Usage()
    cutoff = time.time() - days * 86400
    # Top-level files are sessions; nested ones (…/subagents/*.jsonl) are subagent runs.
    files = [f for f in (CLAUDE_DIR / "projects").rglob("*.jsonl") if f.stat().st_mtime >= cutoff]
    sessions = [f for f in files if f.parent.parent == CLAUDE_DIR / "projects"]
    usage.sessions = len(sessions)
    if files:
        usage.oldest_days = (time.time() - min(f.stat().st_mtime for f in files)) / 86400
    for path in files:
        scan_one_transcript(path, usage, is_session=path in sessions)
    return usage


def scan_one_transcript(path: Path, usage: Usage, is_session: bool) -> None:
    first_turn_seen = not is_session
    try:
        lines = path.open(errors="replace")
    except OSError as err:
        print(f"warning: skipped {path.name}: {err}", file=sys.stderr)
        return
    with lines:
        for line in lines:
            if '"tool_use"' not in line and "command-name" not in line and '"usage"' not in line:
                continue
            try:
                message = json.loads(line).get("message")
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if not first_turn_seen and isinstance(message.get("usage"), dict):
                first_turn_seen = record_baseline(message["usage"], usage)
            count_tools(message.get("content"), usage)


def record_baseline(tokens: dict, usage: Usage) -> bool:
    total = sum(tokens.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    if total > 0:
        usage.baseline_tokens.append(total)
        return True
    return False


def count_tools(content, usage: Usage) -> None:
    if isinstance(content, str):
        usage.skills.update(COMMAND_TAG.findall(content))
        return
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            usage.skills.update(COMMAND_TAG.findall(block.get("text", "")))
        if block.get("type") != "tool_use":
            continue
        name, args = block.get("name", ""), block.get("input") or {}
        if name.startswith("mcp__"):
            usage.mcp["__".join(name.split("__")[:2])] += 1
        elif name == "Skill":
            usage.skills[str(args.get("skill"))] += 1
        elif name in ("Agent", "Task"):
            usage.agents[str(args.get("subagent_type") or "general-purpose")] += 1


def mcp_section(usage: Usage) -> dict:
    config = load_json(CLAUDE_JSON)
    projects = config.get("projects", {})
    per_project = {p: list(v.get("mcpServers", {})) for p, v in projects.items() if v.get("mcpServers")}
    disabled = Counter(s for v in projects.values() for s in v.get("disabledMcpServers", []))
    return {
        "user_scope": list(config.get("mcpServers", {})),
        "project_scope": per_project,
        "disabled_counts": dict(disabled),
        "usage_by_prefix": dict(usage.mcp.most_common()),
        "note": "claude.ai connectors are fetched at runtime and are not in any file. List them from the session's mcp__claude_ai_* tool names.",
    }


def skill_rows(root: Path, source: str, usage: Usage) -> list[dict]:
    rows = []
    for skill_md in sorted(root.glob("*/SKILL.md")) + sorted(root.glob("*/*/SKILL.md")):
        meta = frontmatter(skill_md)
        name = meta.get("name") or skill_md.parent.name
        rows.append({
            "name": name,
            "source": source,
            "description_chars": len(meta.get("description", "")),
            "model_invocable": meta.get("disable-model-invocation", "").lower() != "true",
            "uses": usage.skills.get(name, 0),
            "path": str(skill_md.parent),
        })
    return rows


def plugin_section(settings: dict, usage: Usage) -> tuple[dict, list[dict]]:
    installed = load_json(CLAUDE_DIR / "plugins" / "installed_plugins.json").get("plugins", {})
    enabled = settings.get("enabledPlugins", {})
    plugins, skills = {}, []
    for plugin_id, installs in installed.items():
        install_path = Path(installs[0]["installPath"]) if installs else None
        short = plugin_id.split("@")[0]
        plugin_skills = skill_rows(install_path / "skills", f"plugin:{short}", usage) if install_path else []
        for row in plugin_skills:
            row["uses"] = usage.skills.get(f"{short}:{row['name']}", 0)
        hooks = (install_path / "hooks" / "hooks.json").exists() if install_path else False
        plugins[plugin_id] = {"enabled": bool(enabled.get(plugin_id)), "skills": len(plugin_skills), "has_hooks": hooks}
        skills.extend(plugin_skills)
    synced = list((CLAUDE_DIR / "plugins" / "synced").glob("*/manifest.json"))
    plugins["(claude.ai synced)"] = {"count": sum(len(load_json(m).get("plugins", [])) for m in synced)}
    return plugins, skills


def agents_and_commands(usage: Usage) -> dict:
    agents = []
    for path in sorted((CLAUDE_DIR / "agents").glob("*.md")):
        meta = frontmatter(path)
        description = meta.get("description", "")
        agents.append({
            "name": path.stem,
            "description_chars": len(description),
            "pushy": bool(PUSHY_WORDS.search(description)),
            "uses": usage.agents.get(path.stem, 0),
        })
    commands = [{"name": p.stem, "uses": usage.skills.get(p.stem, 0)} for p in sorted((CLAUDE_DIR / "commands").glob("*.md"))]
    return {"agents": agents, "commands": commands, "builtin_agent_uses": dict(usage.agents.most_common())}


def instructions_section() -> dict:
    files = {}
    for path in [CLAUDE_DIR / "CLAUDE.md", CLAUDE_DIR / "AGENTS.md", HOME / ".codex" / "AGENTS.md", HOME / ".gemini" / "GEMINI.md"]:
        if path.exists():
            files[str(path)] = {"bytes": path.stat().st_size, "symlink_to": str(path.resolve()) if path.is_symlink() else None}
    rules_always, rules_scoped = 0, 0
    for rule in (CLAUDE_DIR / "rules").rglob("*.md"):
        size = rule.stat().st_size
        if "paths" in frontmatter(rule):
            rules_scoped += size
        else:
            rules_always += size
    memories = sorted(
        ((str(m), m.stat().st_size) for m in (CLAUDE_DIR / "projects").glob("*/memory/MEMORY.md")),
        key=lambda item: -item[1],
    )
    return {"files": files, "rules_always_bytes": rules_always, "rules_path_scoped_bytes": rules_scoped, "memory_indexes": memories[:5]}


def settings_section(settings: dict) -> dict:
    keys = ["cleanupPeriodDays", "syncClaudeAiSkills", "syncClaudeAiPlugins", "disableClaudeAiConnectors", "skillOverrides", "effortLevel", "model"]
    return {
        **{k: settings.get(k) for k in keys if k in settings},
        "hook_events": sorted(settings.get("hooks", {})),
        "adhd_always_on": (CLAUDE_DIR / ".i-have-adhd-always").exists(),
    }


def build_report(days: int) -> dict:
    settings = load_json(CLAUDE_DIR / "settings.json")
    usage = scan_transcripts(days)
    plugins, plugin_skills = plugin_section(settings, usage)
    user_skills = skill_rows(CLAUDE_DIR / "skills", "user", usage)
    synced = [r for r in user_skills if "/synced/" in r["path"]]
    for row in synced:
        row["source"] = "claude.ai-synced"
    baseline = usage.baseline_tokens
    return {
        "transcripts": {
            "sessions": usage.sessions,
            "history_days": round(usage.oldest_days, 1),
            "median_first_turn_input_tokens": int(statistics.median(baseline)) if baseline else None,
        },
        "settings": settings_section(settings),
        "mcp": mcp_section(usage),
        "plugins": plugins,
        "skills": user_skills + plugin_skills,
        **agents_and_commands(usage),
        "instructions": instructions_section(),
    }


def print_markdown(report: dict) -> None:
    t = report["transcripts"]
    print(f"# Setup inventory\n\nTranscripts: {t['sessions']} sessions over {t['history_days']} days; "
          f"median first-turn input: {t['median_first_turn_input_tokens']} tokens\n")
    print("## Settings\n```json\n" + json.dumps(report["settings"], indent=2) + "\n```\n")
    print("## MCP\n```json\n" + json.dumps(report["mcp"], indent=2) + "\n```\n")
    print("## Plugins\n```json\n" + json.dumps(report["plugins"], indent=2) + "\n```\n")
    print("## Skills (source, model-invocable, description chars, uses)")
    for s in sorted(report["skills"], key=lambda r: (r["uses"], -r["description_chars"])):
        flag = "auto" if s["model_invocable"] else "manual"
        print(f"- {s['name']} [{s['source']}, {flag}, {s['description_chars']}c, uses={s['uses']}]")
    print("\n## Agents (description chars, pushy wording, uses)")
    for a in report["agents"]:
        print(f"- {a['name']} [{a['description_chars']}c, pushy={a['pushy']}, uses={a['uses']}]")
    print(f"\nBuilt-in/other agent uses: {report['builtin_agent_uses']}")
    print("\n## Commands (uses)\n" + ", ".join(f"{c['name']}={c['uses']}" for c in report["commands"]))
    print("\n## Instructions & memory\n```json\n" + json.dumps(report["instructions"], indent=2) + "\n```")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of markdown")
    parser.add_argument("--days", type=int, default=365, help="transcript window in days (default 365)")
    args = parser.parse_args()
    if not CLAUDE_DIR.exists():
        print(f"No Claude Code config at {CLAUDE_DIR}", file=sys.stderr)
        return 1
    report = build_report(args.days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_markdown(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
