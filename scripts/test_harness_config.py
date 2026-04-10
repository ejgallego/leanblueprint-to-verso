#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config, resolve_chapter_paths  # noqa: E402


def write_config(
    root: Path,
    *,
    chapter_root: str = 'DemoBlueprint/Chapters',
    tex_source_glob: str = './blueprint/src/chapter/*.tex',
) -> None:
    (root / 'verso-harness.toml').write_text(
        '\n'.join(
            [
                'package_name = "DemoBlueprint"',
                'blueprint_main = "BlueprintMain"',
                'formalization_path = "Demo"',
                f'chapter_root = "{chapter_root}"',
                f'tex_source_glob = "{tex_source_glob}"',
                '',
                '[lt]',
                'default_chapters = []',
                '',
            ]
        ),
        encoding='utf-8',
    )


class HarnessConfigTests(unittest.TestCase):
    def test_load_config_reads_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root)
            config = load_config(root)
            self.assertEqual(config.package_name, 'DemoBlueprint')
            self.assertEqual(config.chapter_root, 'DemoBlueprint/Chapters')
            self.assertEqual(config.lt_default_chapters, ())
            self.assertEqual(
                config.lt_node_kind_pairs,
                (
                    ('theorem', 'theorem'),
                    ('definition', 'definition'),
                    ('lemma', 'lemma_'),
                    ('corollary', 'corollary'),
                    ('proof', 'proof'),
                ),
            )
            self.assertFalse(config.native_warnings)
            self.assertTrue(config.strict_external_code)

    def test_custom_node_kind_pairs_extend_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root)
            config_path = root / 'verso-harness.toml'
            config_path.write_text(
                config_path.read_text(encoding='utf-8')
                + '\n[lt.node_kinds]\nproposition = "theorem"\n',
                encoding='utf-8',
            )
            config = load_config(root)
            self.assertIn(('proposition', 'theorem'), config.lt_node_kind_pairs)

    def test_harness_warning_and_strict_link_policy_can_be_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root)
            config_path = root / 'verso-harness.toml'
            config_path.write_text(
                config_path.read_text(encoding='utf-8')
                + '\n[harness]\n'
                + 'native_warnings = true\n'
                + 'strict_external_code = false\n',
                encoding='utf-8',
            )
            config = load_config(root)
            self.assertTrue(config.native_warnings)
            self.assertFalse(config.strict_external_code)

    def test_single_file_tex_source_locator_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, tex_source_glob='./blueprint/src/chapter/main.tex')
            config = load_config(root)
            self.assertEqual(config.tex_source_glob, './blueprint/src/chapter/main.tex')

    def test_missing_config_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SystemExit) as exc:
                load_config(root)
            self.assertIn('missing required verso-harness.toml', str(exc.exception))

    def test_absolute_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root, chapter_root='/abs/path')
            with self.assertRaises(SystemExit) as exc:
                load_config(root)
            self.assertIn('chapter_root must be a relative path', str(exc.exception))

    def test_explicit_path_resolution_still_requires_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(SystemExit) as exc:
                resolve_chapter_paths(root, [Path('Demo.lean')])
            self.assertIn('missing required verso-harness.toml', str(exc.exception))

    def test_legacy_non_port_chapters_is_still_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_config(root)
            config_path = root / 'verso-harness.toml'
            config_path.write_text(
                config_path.read_text(encoding='utf-8')
                + '\n[harness]\nnon_port_chapters = ["DemoBlueprint/Chapters/Legacy.lean"]\n',
                encoding='utf-8',
            )
            config = load_config(root)
            self.assertEqual(config.non_port_chapters, ('DemoBlueprint/Chapters/Legacy.lean',))


if __name__ == '__main__':
    unittest.main()
