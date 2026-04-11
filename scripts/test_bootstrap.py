#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import find_verso_blueprint_dependency  # noqa: E402


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_uses_upstream_toolchain_and_matching_verso_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'demo-project'
            demo = root / 'Demo'
            demo.mkdir(parents=True)
            (demo / 'lean-toolchain').write_text('leanprover/lean4:v4.28.0\n', encoding='utf-8')

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
                    './blueprint/src/chapter/main.tex',
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn('lean-toolchain: leanprover/lean4:v4.28.0', result.stdout)
            self.assertIn('VersoBlueprint ref: v4.28.0', result.stdout)
            self.assertIn('Pages workflow repo: leanprover/verso-blueprint', result.stdout)
            self.assertIn('Pages workflow ref: v4.28.0', result.stdout)

            self.assertEqual(
                (root / 'lean-toolchain').read_text(encoding='utf-8').strip(),
                'leanprover/lean4:v4.28.0',
            )
            lakefile = (root / 'lakefile.lean').read_text(encoding='utf-8')
            self.assertIn('@ "v4.28.0"', lakefile)
            self.assertIn('⟨`weak.verso.blueprint.math.lint, true⟩', lakefile)
            self.assertIn('⟨`weak.verso.blueprint.externalCode.strictResolve, true⟩', lakefile)
            self.assertIn('⟨`weak.verso.code.warnLineLength, .ofNat 0⟩', lakefile)
            self.assertEqual(
                find_verso_blueprint_dependency(root),
                ('leanprover/verso-blueprint', 'v4.28.0'),
            )

            self.assertTrue((root / 'README.md').exists())
            workflow_text = (root / '.github' / 'workflows' / 'blueprint.yml').read_text(
                encoding='utf-8'
            )
            self.assertIn(
                'uses: leanprover/verso-blueprint/.github/workflows/blueprint-pages.yml@v4.28.0',
                workflow_text,
            )
            self.assertIn('checkout_submodules: true', workflow_text)
            self.assertIn('harness_enabled: true', workflow_text)
            config_path = root / 'verso-harness.toml'
            self.assertTrue(config_path.exists())
            config_text = config_path.read_text(encoding='utf-8')
            self.assertIn('package_name = "DemoBlueprint"', config_text)
            self.assertIn('blueprint_main = "BlueprintMain"', config_text)
            self.assertIn('formalization_path = "./Demo"', config_text)
            self.assertIn('chapter_root = "DemoBlueprint/Chapters"', config_text)
            self.assertIn('tex_source_glob = "./blueprint/src/chapter/main.tex"', config_text)
            self.assertIn('default_chapters = []', config_text)
            self.assertIn('[lt.node_kinds]', config_text)
            self.assertIn('proof = "proof"', config_text)
            chapter_dir = root / 'DemoBlueprint' / 'Chapters'
            if chapter_dir.exists():
                self.assertEqual(list(chapter_dir.glob('*.lean')), [])
            self.assertIn('native_warnings = false', config_text)
            self.assertIn('strict_external_code = true', config_text)

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
