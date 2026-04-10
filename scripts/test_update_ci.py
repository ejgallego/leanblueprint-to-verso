#!/usr/bin/env python3
from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

class UpdateCiTests(unittest.TestCase):
    def test_update_ci_renders_reusable_workflow_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "lakefile.lean").write_text(
                '\n'.join(
                    [
                        'import Lake',
                        'open Lake DSL',
                        '',
                        'require Demo from "./Demo"',
                        'require VersoBlueprint from git "https://github.com/leanprover/verso-blueprint.git" @ "v4.28.0"',
                        '',
                        'package DemoBlueprint where',
                    ]
                )
                + '\n',
                encoding='utf-8',
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "update_ci.py"),
                    "--project-root",
                    str(project_root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

            workflow_path = project_root / ".github" / "workflows" / "blueprint.yml"
            workflow_text = workflow_path.read_text(encoding="utf-8")
            self.assertNotIn("__PAGES_WORKFLOW_", workflow_text)
            self.assertIn(
                "uses: leanprover/verso-blueprint/.github/workflows/blueprint-pages.yml@v4.28.0",
                workflow_text,
            )
            self.assertIn("checkout_submodules: true", workflow_text)
            self.assertIn("harness_enabled: true", workflow_text)

            script_path = project_root / "scripts" / "ci-pages.sh"
            self.assertTrue(script_path.exists())
            self.assertTrue(script_path.stat().st_mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
