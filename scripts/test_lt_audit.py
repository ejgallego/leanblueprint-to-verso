#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from lt_audit import (  # noqa: E402
    chapter_build_command,
    classify_warning_owner,
    collect_native_warning_records,
    effective_native_warnings,
    native_warning_check_ok,
    parse_warning_line,
    StepResult,
)


class LtAuditTests(unittest.TestCase):
    def test_chapter_build_command_uses_plain_lake_build_by_default(self) -> None:
        self.assertEqual(
            chapter_build_command("DemoBlueprint.Chapters.Introduction"),
            ["nice", "lake", "build", "DemoBlueprint.Chapters.Introduction"],
        )

    def test_parse_warning_line_extracts_path_when_present(self) -> None:
        self.assertEqual(
            parse_warning_line("DemoBlueprint/Chapters/Intro.lean:12:3: warning: demo"),
            ("DemoBlueprint/Chapters/Intro.lean", "DemoBlueprint/Chapters/Intro.lean:12:3: warning: demo"),
        )
        self.assertEqual(
            parse_warning_line("warning: declaration uses 'sorry'"),
            (None, "warning: declaration uses 'sorry'"),
        )

    def test_native_warning_policy_uses_config_default_until_overridden(self) -> None:
        self.assertFalse(effective_native_warnings(False, None))
        self.assertTrue(effective_native_warnings(True, None))
        self.assertTrue(effective_native_warnings(False, True))
        self.assertFalse(effective_native_warnings(True, False))

    def test_classify_warning_owner_uses_project_ownership(self) -> None:
        project_root = Path("/tmp/demo-project")
        formalization_path = "Demo"
        self.assertEqual(
            classify_warning_owner(
                project_root,
                formalization_path,
                "BlueprintMain.lean",
            ),
            "consumer",
        )
        self.assertEqual(
            classify_warning_owner(
                project_root,
                formalization_path,
                "Demo/Upstream/File.lean",
            ),
            "upstream",
        )
        self.assertEqual(
            classify_warning_owner(
                project_root,
                formalization_path,
                ".lake/packages/verso-blueprint/VersoBlueprint/Foo.lean",
            ),
            "external",
        )

    def test_native_warning_collection_and_scope(self) -> None:
        project_root = Path("/tmp/demo-project")
        result = StepResult(
            name="chapter build",
            command=["nice", "lake", "build", "DemoBlueprint.Chapters.Intro"],
            returncode=0,
            stdout="",
            stderr="\n".join(
                [
                    "BlueprintMain.lean:12:3: warning: consumer warning",
                    "Demo/Upstream/File.lean:8:2: warning: upstream warning",
                    ".lake/packages/verso-blueprint/VersoBlueprint/Foo.lean:4:1: warning: external warning",
                ]
            ),
        )
        records = collect_native_warning_records(project_root, "Demo", result)
        self.assertEqual([record.owner for record in records], ["consumer", "upstream", "external"])
        self.assertFalse(native_warning_check_ok(result, records, "consumer"))
        self.assertFalse(native_warning_check_ok(result, records, "all"))

    def test_native_warning_collection_accepts_upstream_only_in_consumer_scope(self) -> None:
        project_root = Path("/tmp/demo-project")
        result = StepResult(
            name="chapter build",
            command=["nice", "lake", "build", "DemoBlueprint.Chapters.Intro"],
            returncode=0,
            stdout="",
            stderr="Demo/Upstream/File.lean:8:2: warning: upstream warning",
        )
        records = collect_native_warning_records(project_root, "Demo", result)
        self.assertTrue(native_warning_check_ok(result, records, "consumer"))
        self.assertFalse(native_warning_check_ok(result, records, "all"))

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
        self.assertIn("--native-warnings-scope", result.stdout)


if __name__ == "__main__":
    unittest.main()
