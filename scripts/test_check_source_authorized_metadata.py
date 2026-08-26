#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


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


def run_checker(project_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'check_source_authorized_metadata.py'),
            '--project-root',
            str(project_root),
        ],
        cwd=SCRIPT_DIR.parent,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckSourceAuthorizedMetadataTests(unittest.TestCase):
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
