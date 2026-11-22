#!/usr/bin/env python3
"""Read-only inventory of a Claude Code (and Codex/Gemini) setup.

Prints a markdown report of installed MCP servers, plugins, skills, agents,
commands, always-on instructions and memory, with sizes and usage counts
mined from local transcripts, then a ranked list of hygiene findings
(unused, duplicate, failing or never-signed-in items, an overflowing skill
listing, an oversized memory index). It changes nothing on disk.

--live also runs `claude mcp list` (from HOME, so no project .mcp.json is picked
up) to get each server's connection status, including claude.ai connectors.
That launches every user-scoped and plugin server once. Targets are reduced to
scheme://host/path or the executable name, so tokens in URLs or args never print.

Usage: python3 inventory.py [--json] [--days N] [--live]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from urllib.parse import urlsplit
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
# Claude Code lists model-invocable skills in a budget of about 1% of the context
# window (fallback 8,000 characters; override with SLASH_COMMAND_TOOL_CHAR_BUDGET).
# Past it, descriptions are cut and the model can no longer tell when a skill fits.
SKILL_LISTING_BUDGET_CHARS = int(os.environ.get("SLASH_COMMAND_TOOL_CHAR_BUDGET", "8000"))
# MEMORY.md is loaded into every session in its project; past this, trim the index.
MEMORY_INDEX_BUDGET_BYTES = 8000


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
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Only interactive CLI sessions count toward the startup baseline; SDK and
            # headless runs (sdk-py, sdk-ts, -p) start with different prompts.
            if record.get("entrypoint") not in (None, "cli"):
                first_turn_seen = True
            message = record.get("message")
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
    nested = [p for p in sorted(root.glob("*/*/SKILL.md")) if not (p.parent.parent / "SKILL.md").exists()]
    for skill_md in sorted(root.glob("*/SKILL.md")) + nested:
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
        is_enabled = bool(enabled.get(plugin_id))
        plugin_skills = skill_rows(install_path / "skills", f"plugin:{short}", usage) if install_path else []
        for row in plugin_skills:
            row["uses"] = usage.skills.get(f"{short}:{row['name']}", 0)
            row["enabled"] = is_enabled
        hooks = (install_path / "hooks" / "hooks.json").exists() if install_path else False
        servers = list(load_json(install_path / ".mcp.json").get("mcpServers", {})) if install_path else []
        mcp_uses = sum(n for prefix, n in usage.mcp.items() if prefix.startswith(f"mcp__plugin_{short}_"))
        # Plugin commands and agents show up as "<plugin>:<name>"; skill rows already count skills.
        skill_names = {f"{short}:{r['name']}" for r in plugin_skills}
        other_uses = sum(n for k, n in (usage.skills + usage.agents).items() if k.startswith(f"{short}:") and k not in skill_names)
        plugins[plugin_id] = {
            "enabled": is_enabled,
            "skills": len(plugin_skills),
            "mcp_servers": servers,
            "has_hooks": hooks,
            "uses": sum(r["uses"] for r in plugin_skills) + mcp_uses + other_uses,
        }
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
    commands = []
    for path in sorted((CLAUDE_DIR / "commands").glob("*.md")):
        meta = frontmatter(path)
        commands.append({
            "name": path.stem,
            "description_chars": len(meta.get("description", "")),
            "model_invocable": meta.get("disable-model-invocation", "").lower() != "true",
            "uses": usage.skills.get(path.stem, 0),
        })
    return {"agents": agents, "commands": commands, "builtin_agent_uses": dict(usage.agents.most_common())}


def walk_markdown(root: Path) -> list[Path]:
    """All .md files under root, following symlinked folders (install.sh links rules/<lang>)."""
    found = []
    for folder, _dirs, names in os.walk(root, followlinks=True):
        found.extend(Path(folder) / n for n in names if n.endswith(".md"))
    return found


def instructions_section() -> dict:
    files = {}
    for path in [CLAUDE_DIR / "CLAUDE.md", CLAUDE_DIR / "AGENTS.md", HOME / ".codex" / "AGENTS.md", HOME / ".gemini" / "GEMINI.md"]:
        if path.exists():
            files[str(path)] = {"bytes": path.stat().st_size, "symlink_to": str(path.resolve()) if path.is_symlink() else None}
    rules_always, rules_scoped = 0, 0
    for rule in walk_markdown(CLAUDE_DIR / "rules"):
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


def safe_target(raw: str) -> str:
    """Reduce a server target to what's safe to print: scheme://host/path for URLs
    (no userinfo or query, where tokens hide) and the bare executable for commands."""
    raw = raw.replace("(HTTP)", "").replace("(SSE)", "").strip()
    if raw.startswith(("http://", "https://")):
        parts = urlsplit(raw)
        return f"{parts.scheme}://{parts.hostname or ''}{parts.path}".rstrip("/")
    return Path(raw.split()[0]).name if raw else ""


def live_mcp_status() -> list[dict]:
    """Parse `claude mcp list`: one row per server, claude.ai connectors and plugin servers included.

    Runs from HOME so a project's .mcp.json in the current folder is not launched.
    """
    if not shutil.which("claude"):
        return []
    try:
        out = subprocess.run(["claude", "mcp", "list"], capture_output=True, text=True, timeout=180, cwd=HOME).stdout
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"warning: claude mcp list failed: {err}", file=sys.stderr)
        return []
    rows = []
    for line in out.splitlines():
        if ": " not in line or " - " not in line:
            continue
        name, rest = line.split(": ", 1)
        target, status = rest.rsplit(" - ", 1)
        target = safe_target(target)
        state = "connected" if "Connected" in status else "needs_auth" if "authentication" in status else "failed"
        rows.append({"name": name.strip(), "target": target, "state": state})
    return rows


def usage_prefix(server: str) -> str:
    """Map a `claude mcp list` name to the tool-name prefix seen in transcripts."""
    if server.startswith("claude.ai "):
        return "mcp__claude_ai_" + re.sub(r"\W", "_", server[len("claude.ai "):])
    if server.startswith("plugin:"):
        _, plugin, name = server.split(":", 2)
        return f"mcp__plugin_{plugin}_{name}"
    return f"mcp__{server}"


def finding(kind: str, item: str, evidence: str, suggestion: str) -> dict:
    return {"kind": kind, "item": item, "evidence": evidence, "suggestion": suggestion}


def server_findings(report: dict, live: list[dict], history_days: float) -> list[dict]:
    mcp_uses = report["mcp"]["usage_by_prefix"]
    out = []
    by_target: dict[str, list[str]] = {}
    for row in live:
        uses = sum(n for prefix, n in mcp_uses.items() if prefix.lower().startswith(usage_prefix(row["name"]).lower()))
        if row["state"] == "failed":
            out.append(finding("failing", row["name"], "fails to connect at startup", "fix it or remove it"))
        elif row["state"] == "needs_auth" and uses == 0:
            out.append(finding("never signed in", row["name"], "only exposes authenticate tools, 0 uses", "remove, or disconnect on claude.ai"))
        elif uses == 0:
            out.append(finding("unused", row["name"], f"0 tool calls in {history_days:.0f} days", "disable or scope to a project"))
        if row["target"].startswith("http"):
            by_target.setdefault(row["target"], []).append(row["name"])
    for target, names in by_target.items():
        if len(names) > 1:
            out.append(finding("duplicate", " + ".join(names), f"same endpoint {target}", "keep the one you use, remove the rest"))
    if not live:
        scoped = [(s, s) for s in report["mcp"]["user_scope"]]
        scoped += [(s, f"{s} (project {p})") for p, names in report["mcp"]["project_scope"].items() for s in names]
        for server, label in scoped:
            if not any(p.lower().startswith(f"mcp__{server}".lower()) for p in mcp_uses):
                out.append(finding("unused", label, f"0 tool calls in {history_days:.0f} days", "remove (run with --live for status)"))
    return out


def setup_findings(report: dict, history_days: float) -> list[dict]:
    out = []
    for plugin_id, info in report["plugins"].items():
        if info.get("enabled") and info.get("uses") == 0 and (info.get("skills") or info.get("mcp_servers")):
            out.append(finding("unused plugin", plugin_id, f"{info['skills']} skills, {len(info['mcp_servers'])} servers, 0 uses", "disable; re-enable per project when needed"))
    # The listing holds each model-invocable skill and command: its name plus description.
    listed = [s for s in report["skills"] if s["model_invocable"] and s.get("enabled", True)]
    listed += [c for c in report["commands"] if c["model_invocable"]]
    listing_chars = sum(s["description_chars"] + len(s["name"]) for s in listed)
    if listing_chars > SKILL_LISTING_BUDGET_CHARS:
        unused = sum(1 for s in listed if s["uses"] == 0)
        out.append(finding("skill listing overflow", f"{len(listed)} auto skills and commands", f"{listing_chars} description chars vs ~{SKILL_LISTING_BUDGET_CHARS} budget; {unused} never used", "archive unused skills, disable idle plugins, make rare ones manual"))
    for path, size in report["instructions"]["memory_indexes"]:
        if size > MEMORY_INDEX_BUDGET_BYTES:
            out.append(finding("memory index too big", path, f"{size} bytes loaded every session", f"shorten each line to a hook, aim under {MEMORY_INDEX_BUDGET_BYTES} bytes"))
    for agent in report["agents"]:
        if agent["pushy"]:
            out.append(finding("pushy agent", agent["name"], "description says MUST BE USED / PROACTIVELY", "rewrite as when it helps"))
    return out


def build_report(days: int, live: bool = False) -> dict:
    settings = load_json(CLAUDE_DIR / "settings.json")
    usage = scan_transcripts(days)
    plugins, plugin_skills = plugin_section(settings, usage)
    user_skills = skill_rows(CLAUDE_DIR / "skills", "user", usage)
    synced = [r for r in user_skills if "/synced/" in r["path"]]
    for row in synced:
        row["source"] = "claude.ai-synced"
    baseline = usage.baseline_tokens
    report = {
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
    servers = live_mcp_status() if live else []
    report["mcp"]["live"] = servers
    report["findings"] = server_findings(report, servers, usage.oldest_days) + setup_findings(report, usage.oldest_days)
    return report


def print_markdown(report: dict) -> None:
    t = report["transcripts"]
    print(f"# Setup inventory\n\nTranscripts: {t['sessions']} sessions over {t['history_days']} days; "
          f"median first-turn input: {t['median_first_turn_input_tokens']} tokens\n")
    print(f"## Findings ({len(report['findings'])})")
    for f in report["findings"]:
        print(f"- **{f['kind']}**: {f['item']} ({f['evidence']}) -> {f['suggestion']}")
    print()
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
    parser.add_argument("--live", action="store_true", help="also run `claude mcp list` for connection status")
    args = parser.parse_args()
    if not CLAUDE_DIR.exists():
        print(f"No Claude Code config at {CLAUDE_DIR}", file=sys.stderr)
        return 1
    report = build_report(args.days, live=args.live)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_markdown(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
