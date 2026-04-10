#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lt_audit import chapter_build_command, effective_native_warnings  # noqa: E402


class LtAuditTests(unittest.TestCase):
    def test_chapter_build_command_uses_plain_lake_build_by_default(self) -> None:
        self.assertEqual(
            chapter_build_command("DemoBlueprint.Chapters.Introduction", native_warnings=False),
            ["nice", "lake", "build", "DemoBlueprint.Chapters.Introduction"],
        )

    def test_chapter_build_command_can_fail_on_native_warnings(self) -> None:
        self.assertEqual(
            chapter_build_command("DemoBlueprint.Chapters.Introduction", native_warnings=True),
            ["nice", "lake", "--wfail", "build", "DemoBlueprint.Chapters.Introduction"],
        )

    def test_native_warning_policy_uses_config_default_until_overridden(self) -> None:
        self.assertFalse(effective_native_warnings(False, None))
        self.assertTrue(effective_native_warnings(True, None))
        self.assertTrue(effective_native_warnings(False, True))
        self.assertFalse(effective_native_warnings(True, False))

    def test_help_mentions_native_warnings(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "lt_audit.py"), "--help"],
            cwd=SCRIPT_DIR.parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("--native-warnings", result.stdout)


if __name__ == "__main__":
    unittest.main()
