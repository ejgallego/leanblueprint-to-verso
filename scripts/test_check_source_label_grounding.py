#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent


def write_config(root: Path, default_chapters: list[str]) -> None:
    (root / 'verso-harness.toml').write_text(
        '\n'.join(
            [
                'package_name = "DemoBlueprint"',
                'chapter_root = "."',
                'tex_source_glob = "./blueprint/src/chapter/*.tex"',
                '',
                '[lt]',
                f'default_chapters = [{", ".join(repr(path) for path in default_chapters)}]',
                '',
                '[harness]',
                'non_port_chapters = []',
                '',
            ]
        ),
        encoding='utf-8',
    )


class CheckSourceLabelGroundingTests(unittest.TestCase):
    def test_cli_reports_misaligned_verso_id(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "wrapper_id" (lean := "Demo.foo")
Alpha.
:::
```tex "demo/theorem"
\\begin{theorem}
\\label{Demo.foo}
\\lean{Demo.foo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            path = root / 'Demo.lean'
            path.write_text(content, encoding='utf-8')
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'check_source_label_grounding.py'),
                    '--project-root',
                    tmp,
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("verso id 'wrapper_id'", result.stdout)
            self.assertIn("Demo.foo", result.stdout)

    def test_cli_is_quiet_when_ids_match_source_labels(self) -> None:
        content = """#doc (Manual) "Demo" =>

:::theorem "Demo.foo" (lean := "Demo.foo")
Alpha.
:::
```tex "demo/theorem"
\\begin{theorem}
\\label{Demo.foo}
\\lean{Demo.foo}
Alpha.
\\end{theorem}
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, ['Demo.lean'])
            path = root / 'Demo.lean'
            path.write_text(content, encoding='utf-8')
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'check_source_label_grounding.py'),
                    '--project-root',
                    tmp,
                ],
                cwd=SCRIPT_DIR.parent,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertEqual(result.stdout.strip(), '')


if __name__ == '__main__':
    unittest.main()
