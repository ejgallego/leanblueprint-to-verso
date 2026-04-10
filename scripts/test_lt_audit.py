#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import lt_audit  # noqa: E402
from lt_audit import (  # noqa: E402
    chapter_build_command,
    classify_warning_owner,
    collect_native_warning_records,
    effective_native_warnings,
    native_warning_check_ok,
    parse_warning_line,
    StepResult,
)


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class LtAuditTests(unittest.TestCase):
    def make_project(self, root: Path, *, formalization_path: str = "Demo") -> Path:
        write_file(
            root / "verso-harness.toml",
            "\n".join(
                [
                    'package_name = "DemoBlueprint"',
                    'blueprint_main = "BlueprintMain"',
                    f'formalization_path = "{formalization_path}"',
                    'chapter_root = "DemoBlueprint/Chapters"',
                    'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                    "",
                    "[lt]",
                    'default_chapters = ["DemoBlueprint/Chapters/Intro.lean"]',
                    "",
                    "[harness]",
                    "native_warnings = false",
                    "non_port_chapters = []",
                    "",
                ]
            ),
        )
        chapter_path = root / "DemoBlueprint" / "Chapters" / "Intro.lean"
        write_file(chapter_path, '#doc (Manual) "Intro" =>\n\nIntro.\n')
        (root / formalization_path).mkdir(parents=True, exist_ok=True)
        return chapter_path

    def fake_run_step(self, build_stderr: str):
        def inner(project_root: Path, name: str, command: list[str]) -> StepResult:
            if name == "LT source-pair audit":
                return StepResult(name=name, command=command, returncode=0, stdout="pair ok", stderr="")
            if name == "LT similarity report":
                return StepResult(
                    name=name,
                    command=command,
                    returncode=0,
                    stdout="similarity ok",
                    stderr="",
                )
            if name.startswith("chapter build"):
                return StepResult(
                    name=name,
                    command=command,
                    returncode=0,
                    stdout="build ok",
                    stderr=build_stderr,
                )
            raise AssertionError(f"unexpected step: {name}")

        return inner

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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(root / "BlueprintMain.lean", "import DemoBlueprint\n")
            write_file(
                root / "Demo" / "Upstream" / "File.lean",
                "theorem demo : True := by trivial\n",
            )
            write_file(
                root / ".lake" / "packages" / "verso-blueprint" / "VersoBlueprint" / "Foo.lean",
                "def demo : Nat := 0\n",
            )
            self.assertEqual(
                classify_warning_owner(
                    root,
                    "Demo",
                    "BlueprintMain.lean",
                ),
                "consumer",
            )
            self.assertEqual(
                classify_warning_owner(
                    root,
                    "Demo",
                    "Demo/Upstream/File.lean",
                ),
                "upstream",
            )
            self.assertEqual(
                classify_warning_owner(
                    root,
                    "Demo",
                    ".lake/packages/verso-blueprint/VersoBlueprint/Foo.lean",
                ),
                "external",
            )
            write_file(
                root / "vendor" / "SpherePacking" / "Basic" / "PeriodicPacking.lean",
                "theorem demo : True := by trivial\n",
            )
            self.assertEqual(
                classify_warning_owner(
                    root,
                    "vendor",
                    "SpherePacking/Basic/PeriodicPacking.lean",
                ),
                "upstream",
            )

    def test_native_warning_collection_and_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_file(project_root / "BlueprintMain.lean", "import DemoBlueprint\n")
            write_file(
                project_root / "Demo" / "Upstream" / "File.lean",
                "theorem demo : True := by trivial\n",
            )
            write_file(
                project_root / ".lake" / "packages" / "verso-blueprint" / "VersoBlueprint" / "Foo.lean",
                "def demo : Nat := 0\n",
            )
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
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            write_file(
                project_root / "Demo" / "Upstream" / "File.lean",
                "theorem demo : True := by trivial\n",
            )
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

    def test_main_reports_mixed_warning_summary_in_consumer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_path = self.make_project(root)
            write_file(
                root / "Demo" / "Upstream" / "File.lean",
                "theorem demo : True := by trivial\n",
            )
            write_file(
                root / ".lake" / "packages" / "verso-blueprint" / "VersoBlueprint" / "Foo.lean",
                "def demo : Nat := 0\n",
            )
            warning_text = "\n".join(
                [
                    "BlueprintMain.lean:12:3: warning: consumer warning",
                    "Demo/Upstream/File.lean:8:2: warning: upstream warning",
                    ".lake/packages/verso-blueprint/VersoBlueprint/Foo.lean:4:1: warning: external warning",
                ]
            )
            argv = [
                "lt_audit.py",
                "--project-root",
                str(root),
                "--native-warnings",
                str(chapter_path),
            ]
            with patch("lt_audit.run_step", side_effect=self.fake_run_step(warning_text)):
                with patch.object(sys, "argv", argv):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = lt_audit.main()
            output = stdout.getvalue()
            self.assertEqual(result, 1, msg=output)
            self.assertIn("chapter build + native warning check (consumer scope)", output)
            self.assertIn("native warning summary: 3 total, 1 failing under consumer scope", output)
            self.assertIn("consumer-owned: 1 (failing)", output)
            self.assertIn("upstream-transitive: 1 (reported only)", output)
            self.assertIn("external-dependency: 1 (reported only)", output)
            self.assertIn("Overall: FAIL", output)

    def test_main_treats_formalization_relative_paths_as_upstream_in_consumer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_path = self.make_project(root, formalization_path="vendor")
            write_file(
                root / "vendor" / "SpherePacking" / "Basic" / "PeriodicPacking.lean",
                "theorem demo : True := by trivial\n",
            )
            warning_text = "SpherePacking/Basic/PeriodicPacking.lean:1192:8: warning: declaration uses 'sorry'"
            argv = [
                "lt_audit.py",
                "--project-root",
                str(root),
                "--native-warnings",
                str(chapter_path),
            ]
            with patch("lt_audit.run_step", side_effect=self.fake_run_step(warning_text)):
                with patch.object(sys, "argv", argv):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = lt_audit.main()
            output = stdout.getvalue()
            self.assertEqual(result, 0, msg=output)
            self.assertIn("native warning summary: 1 total, 0 failing under consumer scope", output)
            self.assertIn("upstream-transitive: 1 (reported only)", output)
            self.assertIn("Overall: OK", output)

    def test_main_can_fail_transitively_in_all_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter_path = self.make_project(root)
            write_file(
                root / "Demo" / "Upstream" / "File.lean",
                "theorem demo : True := by trivial\n",
            )
            write_file(
                root / ".lake" / "packages" / "verso-blueprint" / "VersoBlueprint" / "Foo.lean",
                "def demo : Nat := 0\n",
            )
            warning_text = "\n".join(
                [
                    "Demo/Upstream/File.lean:8:2: warning: upstream warning",
                    ".lake/packages/verso-blueprint/VersoBlueprint/Foo.lean:4:1: warning: external warning",
                ]
            )
            argv = [
                "lt_audit.py",
                "--project-root",
                str(root),
                "--native-warnings",
                "--native-warnings-scope",
                "all",
                str(chapter_path),
            ]
            with patch("lt_audit.run_step", side_effect=self.fake_run_step(warning_text)):
                with patch.object(sys, "argv", argv):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = lt_audit.main()
            output = stdout.getvalue()
            self.assertEqual(result, 1, msg=output)
            self.assertIn("chapter build + native warning check (all scope)", output)
            self.assertIn("native warning summary: 2 total, 2 failing under all scope", output)
            self.assertIn("upstream-transitive: 1 (failing)", output)
            self.assertIn("external-dependency: 1 (failing)", output)
            self.assertIn("Overall: FAIL", output)

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
