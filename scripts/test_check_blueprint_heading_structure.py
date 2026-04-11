#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


def write_config(root: Path, default_chapters: list[str]) -> None:
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
    (root / 'verso-harness.toml').write_text('\n'.join(lines), encoding='utf-8')


def run_checker(project_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / 'check_blueprint_heading_structure.py'),
            '--project-root',
            str(project_root),
        ],
        cwd=SCRIPT_DIR.parent,
        capture_output=True,
        text=True,
        check=False,
    )


class CheckBlueprintHeadingStructureTests(unittest.TestCase):
    def test_cli_accepts_matching_section_heading(self) -> None:
        content = """#doc (Manual) "Demo" =>

# Introduction

Intro.

```tex
\\section{Introduction}

Intro.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("passed", result.stdout)

    def test_cli_reports_subsection_promoted_to_section(self) -> None:
        content = """#doc (Manual) "Demo" =>

# Examples

Example text.

```tex
\\subsection{Examples}

Example text.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("does not match adjacent TeX subsection", result.stdout)
            self.assertIn("## Examples", result.stdout)

    def test_cli_reports_missing_nested_heading(self) -> None:
        content = """#doc (Manual) "Demo" =>

# Initial definitions

Intro text.

```tex
\\section{Initial definitions}

\\subsection{Scaling Haar measure on a group}

Intro text.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("appears before the next Lean heading", result.stdout)
            self.assertIn("Scaling Haar measure on a group", result.stdout)

    def test_cli_normalizes_texorpdfstring_titles(self) -> None:
        content = """#doc (Manual) "Demo" =>

# Zhat

Intro text.

```tex
\\section{\\texorpdfstring{$\\Zhat$}{Zhat}}

Intro text.
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            (root / 'Demo.lean').write_text(content, encoding='utf-8')
            result = run_checker(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
