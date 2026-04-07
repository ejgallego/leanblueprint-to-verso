#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_writes_required_config_and_passes_harness_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'demo-project'
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'bootstrap.py'),
                    '--project-root',
                    str(root),
                    '--package-name',
                    'DemoBlueprint',
                    '--title',
                    'Demo Blueprint',
                    '--formalization-name',
                    'Demo',
                    '--formalization-path',
                    './Demo',
                    '--tex-source-glob',
                    './blueprint/src/chapter/*.tex',
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            config_path = root / 'verso-harness.toml'
            self.assertTrue(config_path.exists())
            config_text = config_path.read_text(encoding='utf-8')
            self.assertIn('package_name = "DemoBlueprint"', config_text)
            self.assertIn('chapter_root = "DemoBlueprint/Chapters"', config_text)

            check = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'check_harness.py'),
                    '--project-root',
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(check.returncode, 0, msg=check.stdout + check.stderr)


if __name__ == '__main__':
    unittest.main()
