#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_lt_source_freshness import (  # noqa: E402
    audit_project,
    load_deviations,
    witness_fingerprint,
)


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class SourceFreshnessTests(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        chapter = Path("DemoBlueprint/Chapters/Main.lean")
        write_file(
            root / "verso-harness.toml",
            "\n".join(
                [
                    'package_name = "DemoBlueprint"',
                    'blueprint_main = "BlueprintMain"',
                    'formalization_path = "Demo"',
                    'chapter_root = "DemoBlueprint/Chapters"',
                    'tex_source_glob = "blueprint/*.tex"',
                    "",
                    "[lt]",
                    f'default_chapters = ["{chapter}"]',
                    "",
                ]
            ),
        )
        return chapter

    def test_exact_changed_and_unmatched_witnesses_are_distinguished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                "\n".join(
                    [
                        '#doc (Manual) "Main" =>',
                        "",
                        "Exact prose.",
                        "```tex",
                        "Exact prose.",
                        "```",
                        "",
                        ':::theorem "thm:changed"',
                        "Old theorem body.",
                        ":::",
                        "```tex",
                        r"\begin{theorem}",
                        r"\label{thm:changed}",
                        "Old theorem body.",
                        r"\end{theorem}",
                        "```",
                        "",
                        "Unmatched local note.",
                        "```tex",
                        "Unmatched local note.",
                        "```",
                    ]
                ),
            )
            write_file(
                root / "blueprint" / "main.tex",
                "\n".join(
                    [
                        "Exact prose.",
                        r"\begin{theorem}",
                        r"\label{thm:changed}",
                        "New theorem body.",
                        r"\end{theorem}",
                        r"\begin{definition}",
                        r"\label{def:new}",
                        "A newly added source node.",
                        r"\end{definition}",
                    ]
                ),
            )

            report = audit_project(root, [chapter], source_glob="blueprint/*.tex")
            result = report.chapters[0]
            self.assertEqual(
                [item.status for item in result.witnesses],
                ["exact", "content-changed", "unmatched"],
            )
            self.assertEqual(result.stale_witness_count, 2)
            self.assertEqual(result.missing_source_label_count, 1)
            self.assertEqual(result.source_labels[0].label, "def:new")
            self.assertTrue(report.needs_review)

    def test_commented_out_source_nodes_are_not_reported_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                '#doc (Manual) "Main" =>\n\nExact.\n```tex\nExact.\n```\n',
            )
            write_file(
                root / "blueprint" / "main.tex",
                "\n".join(
                    [
                        "Exact.",
                        r"% \begin{lemma}",
                        r"%   \label{lemma:inactive}",
                        r"%   This source node is commented out.",
                        r"% \end{lemma}",
                    ]
                ),
            )

            report = audit_project(root, [chapter], source_glob="blueprint/*.tex")

            self.assertFalse(report.needs_review)
            self.assertEqual(report.chapters[0].source_labels, ())

    def test_fingerprinted_deviations_are_applied_and_expire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            witness = "Intentional local summary."
            write_file(
                root / chapter,
                f'#doc (Manual) "Main" =>\n\nSummary.\n```tex\n{witness}\n```\n',
            )
            write_file(
                root / "blueprint" / "main.tex",
                "Source wording that is deliberately not copied.\n"
                "\\begin{theorem}\n\\label{thm:omitted}\nOmitted.\n\\end{theorem}\n",
            )
            fingerprint = witness_fingerprint(witness)
            write_file(
                root / "lt-source-deviations.toml",
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[witness]]",
                        f'chapter = "{chapter}"',
                        f'fingerprint = "{fingerprint}"',
                        'reason = "The source paragraph is summarized for this reference view."',
                        "",
                        "[[source_label]]",
                        'source = "blueprint/main.tex"',
                        'label = "thm:omitted"',
                        'reason = "This theorem is outside the maintained reference scope."',
                    ]
                ),
            )

            report = audit_project(
                root,
                [chapter],
                source_glob="blueprint/*.tex",
                deviations=load_deviations(root),
            )
            result = report.chapters[0]
            self.assertEqual(result.witnesses[0].status, "allowed")
            # An unmatched witness cannot associate an otherwise-unused source file
            # with a chapter, so the source-label exception is correctly stale.
            self.assertEqual(len(report.errors), 1)
            self.assertIn("unused source-label deviation", report.errors[0])

            write_file(
                root / chapter,
                '#doc (Manual) "Main" =>\n\nSummary.\n```tex\nChanged witness.\n```\n',
            )
            expired = audit_project(
                root,
                [chapter],
                source_glob="blueprint/*.tex",
                deviations=load_deviations(root),
            )
            self.assertEqual(expired.chapters[0].witnesses[0].status, "unmatched")
            self.assertTrue(any("unused witness deviation" in error for error in expired.errors))

    def test_source_label_deviation_is_applied_for_an_active_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                '#doc (Manual) "Main" =>\n\nExact.\n```tex\nExact.\n```\n',
            )
            write_file(
                root / "blueprint" / "main.tex",
                "Exact.\n\\begin{theorem}\n\\label{thm:omitted}\nOmitted.\n\\end{theorem}\n",
            )
            write_file(
                root / "lt-source-deviations.toml",
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[source_label]]",
                        'source = "blueprint/main.tex"',
                        'label = "thm:omitted"',
                        'reason = "This theorem is intentionally omitted."',
                    ]
                ),
            )
            report = audit_project(
                root,
                [chapter],
                source_glob="blueprint/*.tex",
                source_map=((str(chapter), ("blueprint/main.tex",)),),
                deviations=load_deviations(root),
            )
            self.assertFalse(report.needs_review)
            self.assertEqual(report.chapters[0].source_labels[0].status, "allowed")
            self.assertEqual(report.errors, ())

    def test_explicit_source_map_excludes_legacy_files_with_reused_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                "\n".join(
                    [
                        '#doc (Manual) "Main" =>',
                        "",
                        ':::theorem "thm:shared"',
                        "Current body.",
                        ":::",
                        "```tex",
                        r"\begin{theorem}",
                        r"\label{thm:shared}",
                        "Current body.",
                        r"\end{theorem}",
                        "```",
                    ]
                ),
            )
            write_file(
                root / "blueprint" / "current.tex",
                "\\begin{theorem}\n\\label{thm:shared}\nCurrent body.\n\\end{theorem}\n",
            )
            write_file(
                root / "blueprint" / "legacy.tex",
                "\\begin{theorem}\n\\label{thm:shared}\nLegacy body.\n\\end{theorem}\n"
                "\\begin{theorem}\n\\label{thm:legacy-only}\nOld.\n\\end{theorem}\n",
            )
            report = audit_project(
                root,
                [chapter],
                source_glob="blueprint/*.tex",
                source_map=((str(chapter), ("blueprint/current.tex",)),),
            )
            self.assertFalse(report.needs_review)
            self.assertEqual(report.chapters[0].witnesses[0].status, "exact")
            self.assertEqual(report.chapters[0].source_labels, ())

    def test_metadata_changes_and_plastex_branches_are_distinguished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                "\n".join(
                    [
                        '#doc (Manual) "Main" =>',
                        "",
                        ':::theorem "thm:metadata"',
                        "Same theorem body.",
                        ":::",
                        '```tex "thm:metadata"',
                        r"\begin{theorem}\label{thm:metadata}\uses{old}",
                        "Same theorem body.",
                        r"\end{theorem}",
                        "```",
                        "",
                        "The displayed value is $`1`.",
                        "```tex",
                        r"The displayed value is $1$.",
                        r"\begin{equation}",
                        "1",
                        r"\end{equation}",
                        "```",
                    ]
                ),
            )
            write_file(
                root / "blueprint" / "main.tex",
                "\n".join(
                    [
                        r"\begin{theorem}\label{thm:metadata}\uses{new}",
                        "Same theorem body.",
                        r"\end{theorem}",
                        r"The displayed value is $1$.",
                        r"\ifplastex",
                        r"\[1\]",
                        r"\else",
                        r"\begin{equation}",
                        "1",
                        r"\end{equation}",
                        r"\fi",
                    ]
                ),
            )

            report = audit_project(root, [chapter], source_glob="blueprint/*.tex")
            result = report.chapters[0]
            self.assertEqual(
                [item.status for item in result.witnesses],
                ["metadata-changed", "exact"],
            )
            self.assertEqual(result.missing_source_label_count, 0)

    def test_chapter_scoped_audit_ignores_other_chapter_deviations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self.make_project(root)
            second = Path("DemoBlueprint/Chapters/Second.lean")
            write_file(
                root / first,
                '#doc (Manual) "Main" =>\n\nFirst.\n```tex\nFirst.\n```\n',
            )
            write_file(
                root / second,
                '#doc (Manual) "Second" =>\n\nSecond.\n```tex\nSecond.\n```\n',
            )
            write_file(root / "blueprint/first.tex", "First.\n")
            write_file(root / "blueprint/second.tex", "Second.\n")
            write_file(
                root / "lt-source-deviations.toml",
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[witness]]",
                        f'chapter = "{second}"',
                        f'fingerprint = "{witness_fingerprint("Second.")}"',
                        'reason = "A reviewed exception in the other chapter."',
                    ]
                ),
            )
            report = audit_project(
                root,
                [first],
                source_glob="blueprint/*.tex",
                source_map=(
                    (str(first), ("blueprint/first.tex",)),
                    (str(second), ("blueprint/second.tex",)),
                ),
                deviations=load_deviations(root),
            )
            self.assertFalse(report.needs_review)
            self.assertEqual(report.errors, ())

    def test_cli_can_require_current_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            chapter = self.make_project(root)
            write_file(
                root / chapter,
                '#doc (Manual) "Main" =>\n\nLocal.\n```tex\nLocal.\n```\n',
            )
            write_file(root / "blueprint" / "main.tex", "Remote.\n")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_lt_source_freshness.py"),
                    "--project-root",
                    str(root),
                    "--require-current",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("witness_unmatched: 1", result.stdout)
            self.assertIn("current: no", result.stdout)


if __name__ == "__main__":
    unittest.main()
