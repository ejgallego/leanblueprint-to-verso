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
    node_kinds: dict[str, str] | None = None,
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
        '',
    ]
    if node_kinds:
        lines.append('[lt.node_kinds]')
        for tex_kind, verso_kind in node_kinds.items():
            lines.append(f'{tex_kind} = "{verso_kind}"')
        lines.append('')
    lines.extend(
        [
            '[harness]',
            'non_port_chapters = []',
            '',
        ]
    )
    (root / 'verso-harness.toml').write_text('\n'.join(lines), encoding='utf-8')


def run_checker(project_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'check_blueprint_node_kinds.py'),
            '--project-root',
            str(project_root),
        ],
        cwd=SCRIPT_DIR.parent,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckBlueprintNodeKindsTests(unittest.TestCase):
    def test_cli_reports_theorem_vs_lemma_mismatch(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
Foo.
:::
```tex "foo"
\\begin{lemma}
\\label{foo}
Foo.
\\end{lemma}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("adjacent TeX environment 'lemma'", result.stdout)
            self.assertIn(":::lemma_", result.stdout)

    def test_cli_reports_graph_visible_wrapper_over_plain_witness(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
Foo.
:::
```tex "foo"
Foo.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("keep prose as prose", result.stdout)
            self.assertIn("theorem/definition/proof-style object", result.stdout)

    def test_cli_uses_configured_custom_tex_environment_mapping(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "foo"
Foo.
:::
```tex "foo"
\\begin{proposition}
\\label{foo}
Foo.
\\end{proposition}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'], node_kinds={'proposition': 'theorem'})
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("passed", result.stdout)


if __name__ == '__main__':
    unittest.main()
