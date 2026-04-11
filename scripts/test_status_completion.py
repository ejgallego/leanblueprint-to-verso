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
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import status_completion  # noqa: E402
from lt_audit import StepResult  # noqa: E402


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class StatusCompletionTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        write_file(
            root / "verso-harness.toml",
            "\n".join(
                [
                    'package_name = "DemoBlueprint"',
                    'blueprint_main = "BlueprintMain"',
                    'formalization_path = "Demo"',
                    'chapter_root = "DemoBlueprint/Chapters"',
                    'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                    "",
                    "[lt]",
                    'default_chapters = [',
                    '  "DemoBlueprint/Chapters/Clean.lean",',
                    '  "DemoBlueprint/Chapters/Metadata.lean",',
                    '  "DemoBlueprint/Chapters/Low.lean",',
                    '  "DemoBlueprint/Chapters/Unpaired.lean",',
                    ']',
                    "",
                    "[harness]",
                    "native_warnings = false",
                    'non_port_chapters = ["DemoBlueprint/Chapters/PortingStatus.lean"]',
                    "",
                ]
            )
            + "\n",
        )

        write_file(
            root / "DemoBlueprint" / "Chapters" / "Clean.lean",
            "\n".join(
                [
                    '#doc (Manual) "Clean" =>',
                    "",
                    "Alpha beta.",
                    "```tex",
                    "Alpha beta.",
                    "```",
                    "",
                ]
            ),
        )
        write_file(
            root / "DemoBlueprint" / "Chapters" / "Metadata.lean",
            "\n".join(
                [
                    '#doc (Manual) "Metadata" =>',
                    "",
                    ':::definition meta-id (lean := "Wrong.Name")',
                    "Alpha beta.",
                    ":::",
                    "```tex",
                    r"\begin{definition}\lean{Expected.Name}",
                    "Alpha beta.",
                    r"\end{definition}",
                    "```",
                    "",
                ]
            ),
        )
        write_file(
            root / "DemoBlueprint" / "Chapters" / "Low.lean",
            "\n".join(
                [
                    '#doc (Manual) "Low" =>',
                    "",
                    "Completely different prose.",
                    "```tex",
                    "Alpha beta.",
                    "```",
                    "",
                ]
            ),
        )
        write_file(
            root / "DemoBlueprint" / "Chapters" / "Unpaired.lean",
            "\n".join(
                [
                    '#doc (Manual) "Unpaired" =>',
                    "",
                    "This block has no witness.",
                    "",
                ]
            ),
        )
        write_file(
            root / "DemoBlueprint" / "Chapters" / "PortingStatus.lean",
            '#doc (Manual) "Porting Status" =>\n\nStatus only.\n',
        )
        write_file(
            root / "DemoBlueprint" / "Chapters" / "Scratch.lean",
            '#doc (Manual) "Scratch" =>\n\nScratch.\n',
        )

    def test_help_mentions_completion_states(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "status_completion.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("--build", result.stdout)
        self.assertIn("--require-complete", result.stdout)

    def test_status_completion_reports_scope_and_state_transitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_completion.py"),
                    "--project-root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("summary:", result.stdout)
            self.assertIn("  metadata-clean: 1", result.stdout)
            self.assertIn("  lt-audited: 1", result.stdout)
            self.assertIn("  paired: 1", result.stdout)
            self.assertIn("  unpaired: 1", result.stdout)
            self.assertIn("  non-port: 1", result.stdout)
            self.assertIn("  untracked: 1", result.stdout)
            self.assertIn("[metadata-clean] DemoBlueprint/Chapters/Clean.lean", result.stdout)
            self.assertIn("[lt-audited] DemoBlueprint/Chapters/Metadata.lean", result.stdout)
            self.assertIn("[paired] DemoBlueprint/Chapters/Low.lean", result.stdout)
            self.assertIn("[unpaired] DemoBlueprint/Chapters/Unpaired.lean", result.stdout)
            self.assertIn("[non-port] DemoBlueprint/Chapters/PortingStatus.lean", result.stdout)
            self.assertIn("[untracked] DemoBlueprint/Chapters/Scratch.lean", result.stdout)

    def test_status_completion_can_require_build_clean_done_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_file(
                root / "verso-harness.toml",
                "\n".join(
                    [
                        'package_name = "DemoBlueprint"',
                        'blueprint_main = "BlueprintMain"',
                        'formalization_path = "Demo"',
                        'chapter_root = "DemoBlueprint/Chapters"',
                        'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                        "",
                        "[lt]",
                        'default_chapters = ["DemoBlueprint/Chapters/Clean.lean"]',
                        "",
                        "[harness]",
                        "native_warnings = false",
                        "non_port_chapters = []",
                        "",
                    ]
                )
                + "\n",
            )
            write_file(
                root / "DemoBlueprint" / "Chapters" / "Clean.lean",
                '#doc (Manual) "Clean" =>\n\nAlpha beta.\n```tex\nAlpha beta.\n```\n',
            )
            (root / "Demo").mkdir(parents=True, exist_ok=True)

            argv = [
                "status_completion.py",
                "--project-root",
                str(root),
                "--build",
                "--require-complete",
            ]
            with patch(
                "status_completion.run_step",
                return_value=StepResult(
                    name="chapter build",
                    command=["nice", "lake", "build", "DemoBlueprint.Chapters.Clean"],
                    returncode=0,
                    stdout="ok",
                    stderr="",
                ),
            ):
                with patch.object(sys, "argv", argv):
                    stdout = io.StringIO()
                    with contextlib.redirect_stdout(stdout):
                        result = status_completion.main()
            output = stdout.getvalue()
            self.assertEqual(result, 0, msg=output)
            self.assertIn("  done: 1", output)
            self.assertIn("  complete: yes", output)
            self.assertIn("[done] DemoBlueprint/Chapters/Clean.lean", output)


if __name__ == "__main__":
    unittest.main()
