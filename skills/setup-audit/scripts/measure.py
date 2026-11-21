#!/usr/bin/env python3
"""Measure Claude Code's startup context: the tokens sent before you type anything.

Runs `claude -p "Reply with just OK." --output-format json` from a directory and sums
input + cache-creation + cache-read tokens of that first request. Each run costs real
money (roughly $0.01-$0.30 on Opus, less when the prompt cache is warm), so ask first.

Conditions:
  current        your setup as-is
  no-connectors  same, with claude.ai connectors off (ENABLE_CLAUDEAI_MCP_SERVERS=false)

In headless mode the first request can go out before every MCP server has connected,
so "current" varies between runs and undercounts connectors versus an interactive
session. The no-connectors number is stable. Use --reps to see the spread.

Usage: measure.py [--cwd DIR] [--reps N] [--conditions current,no-connectors] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

PROMPT = "Reply with just OK."
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
CONDITIONS = {
    "current": {},
    "no-connectors": {"ENABLE_CLAUDEAI_MCP_SERVERS": "false"},
}
TIMEOUT_SECONDS = 180


def run_once(cwd: Path, extra_env: dict[str, str]) -> dict:
    env = {**os.environ, **extra_env}
    try:
        proc = subprocess.run(
            ["claude", "-p", PROMPT, "--output-format", "json"],
            cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {TIMEOUT_SECONDS}s"}
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": f"claude exited {proc.returncode}: {proc.stderr.strip()[:200] or 'no JSON output'}"}
    if result.get("is_error"):
        return {"error": str(result.get("result"))[:200]}
    usage = result.get("usage", {})
    return {"tokens": sum(usage.get(f, 0) for f in TOKEN_FIELDS), "cost_usd": result.get("total_cost_usd")}


def summarize(runs: list[dict]) -> dict:
    tokens = [r["tokens"] for r in runs if "tokens" in r]
    errors = [r["error"] for r in runs if "error" in r]
    if not tokens:
        return {"runs": len(runs), "errors": errors}
    return {
        "runs": len(runs),
        "median": int(statistics.median(tokens)),
        "min": min(tokens),
        "max": max(tokens),
        "cost_usd": round(sum(r.get("cost_usd") or 0 for r in runs), 4),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cwd", default=".", help="directory to start the session in (default: here)")
    parser.add_argument("--reps", type=int, default=1, help="runs per condition (default 1)")
    parser.add_argument("--conditions", default="current,no-connectors")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if shutil.which("claude") is None:
        print("claude CLI not found on PATH", file=sys.stderr)
        return 1
    cwd = Path(args.cwd).expanduser().resolve()
    if not cwd.is_dir():
        print(f"not a directory: {cwd}", file=sys.stderr)
        return 1
    names = [c.strip() for c in args.conditions.split(",") if c.strip()]
    unknown = [n for n in names if n not in CONDITIONS]
    if unknown:
        print(f"unknown condition(s): {', '.join(unknown)}; choose from {', '.join(CONDITIONS)}", file=sys.stderr)
        return 1

    report = {name: summarize([run_once(cwd, CONDITIONS[name]) for _ in range(args.reps)]) for name in names}
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"Startup context from {cwd} (prompt: {PROMPT!r})\n")
    print(f"{'condition':<15} {'median':>8} {'min':>8} {'max':>8} {'runs':>5} {'cost $':>8}")
    for name, s in report.items():
        if "median" in s:
            print(f"{name:<15} {s['median']:>8} {s['min']:>8} {s['max']:>8} {s['runs']:>5} {s['cost_usd']:>8}")
        for err in s["errors"]:
            print(f"{name:<15} error: {err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
