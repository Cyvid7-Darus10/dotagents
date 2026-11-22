"""Tests for status.py. Run: python3 -I -m unittest discover -s scripts"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status  # noqa: E402

ADHD = "i-have-adhd@i-have-adhd"


class StatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.claude = root / "claude"
        for name in ("alpha", "beta"):
            (self.repo / "skills" / name).mkdir(parents=True)
        (self.repo / "global").mkdir()
        (self.repo / "global" / "AGENTS.md").write_text("x")
        (self.repo / "settings.json").write_text(json.dumps({"permissions": {"deny": ["Bash(nc *)"]}}))
        (self.claude / "skills").mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def rows(self) -> dict[str, status.Row]:
        return {r.name: r for r in status.collect(self.repo, self.claude, self.claude / ".claude.json")}

    def install_adhd(self, enabled: bool) -> None:
        (self.claude / "plugins").mkdir(exist_ok=True)
        (self.claude / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {ADHD: [{}]}}))
        (self.claude / "settings.json").write_text(json.dumps({"enabledPlugins": {ADHD: enabled}}))

    def test_fresh_setup_reports_everything_off(self) -> None:
        rows = self.rows()
        self.assertEqual("off", rows["Skills"].state)
        self.assertEqual("off", rows["ADHD mode"].state)
        self.assertEqual("not run", rows["Cleanup audit"].state)

    def test_partly_linked_skills_are_partial(self) -> None:
        (self.claude / "skills" / "alpha").symlink_to(self.repo / "skills" / "alpha")
        row = self.rows()["Skills"]
        self.assertEqual(("partial", "1 of 2 linked"), (row.state, row.detail))

    def test_disabled_adhd_plugin_is_reported_as_disabled_not_on(self) -> None:
        self.install_adhd(enabled=False)
        self.assertEqual("disabled", self.rows()["ADHD mode"].state)

    def test_adhd_with_flag_file_is_always_on(self) -> None:
        self.install_adhd(enabled=True)
        (self.claude / ".i-have-adhd-always").touch()
        self.assertEqual("on", self.rows()["ADHD mode"].state)

    def test_installed_notes_hook_is_reported_on(self) -> None:
        hook = {"type": "command", "command": 'python3 -I "$HOME/.claude/skills/project-notes/scripts/notes.py" brief'}
        (self.claude / "settings.json").write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [hook]}]}}))
        self.assertEqual("on", self.rows()["personal_docs hook"].state)

    def test_audit_backup_marks_cleanup_as_run(self) -> None:
        (self.claude / "backups" / "pre-audit-20260102-030405").mkdir(parents=True)
        row = self.rows()["Cleanup audit"]
        self.assertEqual(("on", "last run 2026-01-02"), (row.state, row.detail))


if __name__ == "__main__":
    unittest.main()
