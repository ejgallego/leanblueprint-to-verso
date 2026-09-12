#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
from check_lt_source_freshness import witness_fingerprint


def write_config(
    root: Path,
    default_chapters: list[str],
    *,
    lean_target_aliases: dict[str, str] | None = None,
    unresolved_lean_targets: list[str] | None = None,
) -> None:
    lines = [
        'package_name = "DemoBlueprint"',
        'blueprint_main = "BlueprintMain"',
        'formalization_path = "Demo"',
        'chapter_root = "."',
        'tex_source_glob = "./blueprint/src/chapter/*.tex"',
        '',
        '[lt]',
        f'default_chapters = [{", ".join(repr(path) for path in default_chapters)}]',
    ]
    if unresolved_lean_targets:
        values = ', '.join(repr(target) for target in unresolved_lean_targets)
        lines.append(f'unresolved_lean_targets = [{values}]')
    if lean_target_aliases:
        lines.extend(['', '[lt.lean_target_aliases]'])
        lines.extend(
            f'{source!r} = {target!r}'
            for source, target in lean_target_aliases.items()
        )
    lines.append('')
    (root / 'verso-harness.toml').write_text('\n'.join(lines), encoding='utf-8')


def run_checker(project_root: Path, *chapters: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'check_source_authorized_metadata.py'),
            '--project-root',
            str(project_root),
            *chapters,
        ],
        cwd=SCRIPT_DIR.parent,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckSourceAuthorizedMetadataTests(unittest.TestCase):
    def test_reference_correction_chapter_must_exist_but_can_be_outside_focused_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean', 'Other.lean'])
            (root / "Demo.lean").write_text('#doc (Manual) "Demo" =>\n')
            (root / "lt-source-deviations.toml").write_text(
                'version = 1\n\n[[reference]]\nchapter = "Other.lean"\n'
                f'fingerprint = "{"0" * 64}"\n'
                'source_label = "old_label"\ntarget_label = "current_label"\n'
                'reason = "Reviewed correction in a different chapter."\n'
            )
            result = run_checker(root, "Demo.lean")
            self.assertEqual(result.returncode, 1)
            self.assertIn("correction chapter does not exist: Other.lean", result.stderr)
            (root / "Other.lean").write_text('#doc (Manual) "Other" =>\n')
            result = run_checker(root, "Demo.lean")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = run_checker(root)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unused reference correction Other.lean", result.stdout)

    def test_reviewed_reference_correction_is_narrow_and_expires(self) -> None:
        witness = r"See lemma~\ref{old_label}."
        fingerprint = witness_fingerprint(witness)
        cases = [
            ("accepted", {}, 0, ""),
            ("wrong fingerprint", {"fingerprint": "0" * 64}, 1, "unused reference correction"),
            ("changed witness", {"witness": witness + " New text."}, 1, "unused reference correction"),
            ("upstream fixed", {"upstream_witness": r"See lemma~\ref{current_label}."}, 1, "unused reference correction"),
            ("source reference absent", {"source_label": "not_in_witness"}, 1, "unused reference correction"),
            ("target absent", {"target": "missing"}, 1, "unused reference correction"),
            ("old label still defined", {"old_defined": True}, 1, "unused reference correction"),
            ("unrelated bpref", {"extra": 'and {bpref "unreviewed"}[]'}, 1, "extra bprefs ['unreviewed']"),
            ("uses unchanged", {"extra": 'and {uses "current_label"}[]'}, 1, "extra uses ['current_label']"),
            ("expired correction", {"witness": r"See lemma~\ref{current_label}."}, 1, "unused reference correction"),
            ("no local correction", {"local_label": "old_label"}, 1, "unused reference correction"),
        ]
        for name, changes, expected_code, expected_message in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_config(root, ['Demo.lean'])
                target = changes.get("target", "current_label")
                local_label = changes.get("local_label", target)
                body = changes.get("witness", witness)
                content = (
                    '#doc (Manual) "Demo" =>\n\n'
                    f'See {{bpref "{local_label}"}}[] {changes.get("extra", "")}.\n'
                    f'```tex\n{body}\n```\n'
                )
                (root / "Demo.lean").write_text(content)
                source_dir = root / "blueprint/src/chapter"
                source_dir.mkdir(parents=True)
                source = r"\begin{lemma}\label{current_label}Target.\end{lemma}"
                if changes.get("old_defined"):
                    source += r"\begin{lemma}\label{old_label}Old target.\end{lemma}"
                (source_dir / "main.tex").write_text(changes.get("upstream_witness", witness) + "\n" + source)
                (root / "lt-source-deviations.toml").write_text(
                    'version = 1\n\n[[reference]]\nchapter = "Demo.lean"\n'
                    f'fingerprint = "{changes.get("fingerprint", fingerprint)}"\n'
                    f'source_label = "{changes.get("source_label", "old_label")}"\n'
                    f'target_label = "{target}"\n'
                    'reason = "Reviewed stale prose reference; keep the original witness."\n'
                )
                result = run_checker(root)
                self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
                self.assertIn(expected_message, result.stdout)

    def test_reference_correction_cannot_target_an_inactive_source_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            with (root / "verso-harness.toml").open("a") as config:
                config.write('[lt.source_files]\n"Demo.lean" = ["blueprint/src/chapter/main.tex"]\n')
            witness = r"See lemma~\ref{old_label}."
            (root / "Demo.lean").write_text(
                '#doc (Manual) "Demo" =>\n\nSee {bpref "current_label"}[].\n'
                f'```tex\n{witness}\n```\n'
            )
            source_dir = root / "blueprint/src/chapter"
            source_dir.mkdir(parents=True)
            (source_dir / "main.tex").write_text(witness)
            (source_dir / "inactive.tex").write_text(
                r"\begin{lemma}\label{current_label}Target.\end{lemma}"
            )
            (root / "lt-source-deviations.toml").write_text(
                'version = 1\n\n[[reference]]\nchapter = "Demo.lean"\n'
                f'fingerprint = "{witness_fingerprint(witness)}"\n'
                'source_label = "old_label"\ntarget_label = "current_label"\n'
                'reason = "Reviewed stale prose reference."\n'
            )
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("unused reference correction", result.stdout)

    def test_cli_reports_local_only_uses(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::proof "foo"
{uses "bar"}[]
Alpha.
:::
```tex "foo" (slot := proof)
\\begin{proof}
Alpha.
\\end{proof}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("extra uses ['bar']", result.stdout)

    def test_cli_reports_local_only_block_uses(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::proof "foo" (uses := "bar, baz")
Alpha.
:::
```tex "foo" (slot := proof)
\\begin{proof}
Alpha.
\\end{proof}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("extra uses ['bar', 'baz']", result.stdout)

    def test_cli_reports_local_only_bpref(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::proof "foo"
{bpref "bar"}[]
Alpha.
:::
```tex "foo" (slot := proof)
\\begin{proof}
Alpha.
\\end{proof}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("extra bprefs ['bar']", result.stdout)

    def test_cli_reports_local_only_lean_attachment(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (lean := "Demo.foo")
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("extra lean ['Demo.foo']", result.stdout)

    def test_cli_accepts_source_authorized_metadata(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (lean := "Demo.foo")
{uses "bar"}[]
{bpref "baz"}[]
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.foo}
\\uses{bar}
By theorem~\\ref{baz}.
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_current_declaration_authorized_by_source_alias(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (lean := "Demo.currentName")
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.oldName}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(
                root,
                ['Demo.lean'],
                lean_target_aliases={'Demo.oldName': 'Demo.currentName'},
            )
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_explicitly_unresolved_source_target_without_local_link(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.notImplemented}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(
                root,
                ['Demo.lean'],
                unresolved_lean_targets=['Demo.notImplemented'],
            )
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_block_uses_authorized_by_source(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (lean := "Demo.foo") (uses := "bar, baz") (uses_intent := "auxiliary")
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.foo}
\\uses{bar,baz}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_source_label_alias_for_lean_named_use(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (uses := "target_label")
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\uses{Demo.target}
Alpha.
\\end{theorem}
```
"""
        source = """\\begin{definition}
\\lean{Demo.target}
\\label{target_label}
Target.
\\end{definition}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            source_dir = root / 'blueprint' / 'src' / 'chapter'
            source_dir.mkdir(parents=True)
            (source_dir / 'main.tex').write_text(source, encoding='utf-8')
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_source_label_alias_for_lean_named_ref(self) -> None:
        content = """#doc (Manual) "Demo" =>

See {bpref "target_label"}[].
```tex
See theorem~\\ref{Demo.target}.
```
"""
        source = """\\begin{definition}
\\lean{Demo.target}
\\label{target_label}
Target.
\\end{definition}
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            source_dir = root / 'blueprint' / 'src' / 'chapter'
            source_dir.mkdir(parents=True)
            (source_dir / 'main.tex').write_text(source, encoding='utf-8')
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_dependency_list_label_uses_authorized_by_source(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (uses := ["bar", -"excluded", Demo.formalDep])
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\uses{bar}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_reports_local_only_dependency_list_label_uses(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (uses := ["bar", -"excluded", Demo.formalDep])
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("extra uses ['bar']", result.stdout)
            self.assertNotIn("excluded", result.stdout)
            self.assertNotIn("Demo.formalDep", result.stdout)

    def test_cli_accepts_inline_use_metadata(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
This uses {uses "bar" (intent := "technical")}[Bar].
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\uses{bar}
This uses Bar.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_auto_deps_option_without_source_obligation(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (lean := "Demo.foo") (autoDeps := true)
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.foo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_ignores_automatic_uses_without_source_witness(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo" (uses := "auto_header") (uses_origin := "automatic")
This uses {uses "auto_inline" (origin := "automatic")}[generated edge].
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
This has no manual dependency metadata.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_accepts_bprefs_authorized_by_cleveref(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
See {bpref "bar"}[] and {bpref "baz"}[].
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
See Theorems~\\Cref{bar,baz}.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')

    def test_cli_allows_missing_local_metadata(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
Alpha.
:::
```tex "foo"
\\begin{theorem}
\\label{foo}
\\lean{Demo.foo}
\\uses{bar}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
