#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from check_lt_source_pairs import audit_file, parse_blocks  # noqa: E402


class CheckLtSourcePairsTests(unittest.TestCase):
    def test_metadata_blocks_are_transparent_for_tex_pairing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Chapter.lean"
            path.write_text(
                "\n".join(
                    [
                        'import Verso',
                        '',
                        '#doc (Manual) "Demo" =>',
                        '',
                        '# Tagged Section',
                        '%%%',
                        'tag := "tagged-section"',
                        '%%%',
                        '',
                        'Alpha.',
                        '%%%',
                        'tag := "alpha"',
                        '%%%',
                        '',
                        '```tex',
                        'Alpha.',
                        '```',
                        '',
                    ]
                ),
                encoding="utf-8",
            )

            self.assertEqual(audit_file(path), [])
            self.assertNotIn("metadata", {block.kind for block in parse_blocks(path)})


if __name__ == "__main__":
    unittest.main()
