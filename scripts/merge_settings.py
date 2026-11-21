#!/usr/bin/env python3
"""Merge this repo's settings.json template into the user's ~/.claude/settings.json.

Never overwrites a value the user already set. It only:
  - adds cleanupPeriodDays (90) if missing
  - unions permissions.deny
  - with --hooks: adds the template's hook entries whose command isn't present yet
  - with --sounds: adds Stop/Notification sound hooks

Usage: merge_settings.py TEMPLATE TARGET [--hooks] [--sounds] [--dry-run]
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

SOUND_HOOKS = {
    "Stop": 'afplay "$HOME/.claude/sounds/jobs-done.mp3" &',
    "Notification": 'afplay "$HOME/.claude/sounds/work-work.mp3" &',
}


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as err:
        sys.exit(f"merge_settings: {path} is not valid JSON ({err}); fix it and re-run")


def existing_commands(hooks: dict) -> set[str]:
    return {h.get("command", "") for groups in hooks.values() for g in groups for h in g.get("hooks", [])}


def merge_hooks(target_hooks: dict, extra: dict) -> list[str]:
    """Return a list of added commands; mutates only the copy passed in."""
    present = existing_commands(target_hooks)
    added = []
    for event, groups in extra.items():
        for group in groups:
            new = [h for h in group.get("hooks", []) if h.get("command") not in present]
            if new:
                target_hooks.setdefault(event, []).append({**group, "hooks": new})
                added.extend(h["command"] for h in new)
    return added


def merge(template: dict, current: dict, hooks: bool, sounds: bool) -> tuple[dict, list[str]]:
    result = copy.deepcopy(current)
    changes = []
    if "cleanupPeriodDays" not in result:
        result["cleanupPeriodDays"] = 90
        changes.append("cleanupPeriodDays = 90")
    deny = result.setdefault("permissions", {}).setdefault("deny", [])
    for rule in template.get("permissions", {}).get("deny", []):
        if rule not in deny:
            deny.append(rule)
            changes.append(f"deny {rule}")
    if hooks:
        changes += [f"hook {c}" for c in merge_hooks(result.setdefault("hooks", {}), template.get("hooks", {}))]
    if sounds:
        extra = {e: [{"hooks": [{"type": "command", "command": c}]}] for e, c in SOUND_HOOKS.items()}
        changes += [f"hook {c}" for c in merge_hooks(result.setdefault("hooks", {}), extra)]
    return result, changes


def main(argv: list[str]) -> int:
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    template_path, target_path = Path(paths[0]), Path(paths[1])
    merged, changes = merge(read_json(template_path), read_json(target_path), "--hooks" in argv, "--sounds" in argv)
    for change in changes:
        print(f"  {'[dry-run] ' if '--dry-run' in argv else ''}settings: {change}")
    if not changes:
        print("  settings: nothing to change")
    if changes and "--dry-run" not in argv:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = target_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(merged, indent=2) + "\n")
        os.replace(tmp, target_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
