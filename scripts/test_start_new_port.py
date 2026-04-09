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
    def test_start_new_port_uses_upstream_toolchain_and_matching_verso_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            formalization = tmp_root / 'formalization-src'
            formalization.mkdir()
            run(['git', 'init'], cwd=formalization)
            (formalization / 'README.md').write_text('demo\n', encoding='utf-8')
            (formalization / 'lean-toolchain').write_text('leanprover/lean4:v4.28.0\n', encoding='utf-8')
            run(['git', 'add', 'README.md', 'lean-toolchain'], cwd=formalization)
            commit = run(
                [
                    'git', '-c', 'user.name=Codex', '-c', 'user.email=codex@example.com',
                    'commit', '-m', 'init'
                ],
                cwd=formalization,
            )
            self.assertEqual(commit.returncode, 0, msg=commit.stdout + commit.stderr)

            project = tmp_root / 'demo-verso'
            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'start_new_port.py'),
                    '--project-root', str(project),
                    '--package-name', 'DemoBlueprint',
                    '--title', 'Demo Blueprint',
                    '--formalization-name', 'Demo',
                    '--formalization-remote', str(formalization),
                    '--formalization-path', 'Demo',
                    "--tex-source-glob",
                    "./blueprint/src/chapter/main.tex",
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('lean-toolchain: leanprover/lean4:v4.28.0', result.stdout)
            self.assertIn('VersoBlueprint ref: lean-v4.28.0', result.stdout)
            self.assertTrue((project / '.git').exists())
            self.assertTrue((project / '.gitmodules').exists())
            self.assertTrue((project / 'Demo').exists())
            self.assertEqual(
                (project / 'lean-toolchain').read_text(encoding='utf-8').strip(),
                'leanprover/lean4:v4.28.0',
            )
            lakefile = (project / 'lakefile.lean').read_text(encoding='utf-8')
            self.assertIn('@ "lean-v4.28.0"', lakefile)
            self.assertTrue((project / 'README.md').exists())
            self.assertTrue((project / 'verso-harness.toml').exists())
            self.assertTrue((project / 'BlueprintMain.lean').exists())
            config_text = (project / 'verso-harness.toml').read_text(encoding='utf-8')
            self.assertIn(
                'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                config_text,
            )
            self.assertIn('[lt.node_kinds]', config_text)
            self.assertIn('proof = "proof"', config_text)

            check = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / 'check_harness.py'),
                    '--project-root',
                    str(project),
                ],
                cwd=ROOT,
            )
            self.assertEqual(check.returncode, 0, msg=check.stdout + check.stderr)


if __name__ == '__main__':
    unittest.main()
