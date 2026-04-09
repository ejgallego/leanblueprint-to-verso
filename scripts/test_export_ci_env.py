#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent


class ExportCiEnvTests(unittest.TestCase):
    def test_exports_formalization_path_and_blueprint_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "verso-harness.toml").write_text(
                """package_name = \"DemoBlueprint\"
blueprint_main = \"DemoMain\"
formalization_path = \"Demo\"
chapter_root = \"DemoBlueprint/Chapters\"
tex_source_glob = \"./blueprint/src/chapter/main.tex\"

[lt]
default_chapters = [\"DemoBlueprint/Chapters/Introduction.lean\"]

[harness]
non_port_chapters = []
""",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "export_ci_env.py"),
                    "--project-root",
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("formalization_path=Demo", result.stdout)
            self.assertIn("blueprint_main_path=DemoMain.lean", result.stdout)


if __name__ == "__main__":
    unittest.main()
