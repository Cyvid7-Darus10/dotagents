"""Tests for inventory.py findings. Run: python3 -I -m unittest discover -s skills/setup-audit/scripts"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inventory  # noqa: E402


def report_with(user_scope: list[str], project_scope: dict[str, list[str]], uses: dict[str, int]) -> dict:
    return {"mcp": {"user_scope": user_scope, "project_scope": project_scope, "usage_by_prefix": uses}}


class ServerFindingsTest(unittest.TestCase):
    def test_unused_project_scoped_server_is_flagged_without_live(self) -> None:
        report = report_with([], {"/home/someone": ["github"]}, {})
        found = inventory.server_findings(report, live=[], history_days=30)
        self.assertIn(("unused", "github (project /home/someone)"), [(f["kind"], f["item"]) for f in found])

    def test_used_project_scoped_server_is_not_flagged(self) -> None:
        report = report_with([], {"/home/someone": ["github"]}, {"mcp__github": 5})
        found = inventory.server_findings(report, live=[], history_days=30)
        self.assertEqual([], found)

    def test_unused_user_scoped_server_is_still_flagged(self) -> None:
        report = report_with(["docs"], {}, {})
        found = inventory.server_findings(report, live=[], history_days=30)
        self.assertEqual(["docs"], [f["item"] for f in found])


if __name__ == "__main__":
    unittest.main()
