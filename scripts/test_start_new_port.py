#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class StartNewPortTests(unittest.TestCase):
    def test_start_new_port_creates_canonical_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            formalization = tmp_root / "formalization-src"
            formalization.mkdir()
            run(["git", "init"], cwd=formalization)
            (formalization / "README.md").write_text("demo\n", encoding="utf-8")
            run(["git", "add", "README.md"], cwd=formalization)
            commit = run(
                [
                    "git",
                    "-c",
                    "user.name=Codex",
                    "-c",
                    "user.email=codex@example.com",
                    "commit",
                    "-m",
                    "init",
                ],
                cwd=formalization,
            )
            self.assertEqual(commit.returncode, 0, msg=commit.stdout + commit.stderr)

            project = tmp_root / "demo-verso"
            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "start_new_port.py"),
                    "--project-root",
                    str(project),
                    "--package-name",
                    "DemoBlueprint",
                    "--title",
                    "Demo Blueprint",
                    "--formalization-name",
                    "Demo",
                    "--formalization-remote",
                    str(formalization),
                    "--formalization-path",
                    "Demo",
                    "--tex-source-glob",
                    "./blueprint/src/chapter/*.tex",
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue((project / ".git").exists())
            self.assertTrue((project / ".gitmodules").exists())
            self.assertTrue((project / "Demo").exists())
            self.assertTrue((project / "verso-harness.toml").exists())
            self.assertTrue((project / "lakefile.lean").exists())
            self.assertTrue((project / "BlueprintMain.lean").exists())

            check = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "check_harness.py"),
                    "--project-root",
                    str(project),
                ],
                cwd=ROOT,
            )
            self.assertEqual(check.returncode, 0, msg=check.stdout + check.stderr)


if __name__ == "__main__":
    unittest.main()
