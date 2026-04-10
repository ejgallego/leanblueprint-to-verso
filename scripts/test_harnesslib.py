#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import find_verso_blueprint_dependency, parse_github_repo_slug  # noqa: E402


class HarnessLibTests(unittest.TestCase):
    def test_parse_github_repo_slug_accepts_ssh_and_https(self) -> None:
        self.assertEqual(
            parse_github_repo_slug("git@github.com:leanprover/verso-blueprint.git"),
            "leanprover/verso-blueprint",
        )
        self.assertEqual(
            parse_github_repo_slug("https://github.com/leanprover/verso-blueprint"),
            "leanprover/verso-blueprint",
        )

    def test_find_verso_blueprint_dependency_reads_lakefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lakefile.lean").write_text(
                'require VersoBlueprint from git "https://github.com/leanprover/verso-blueprint.git" @ "v4.28.0"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                find_verso_blueprint_dependency(root),
                ("leanprover/verso-blueprint", "v4.28.0"),
            )

    def test_find_verso_blueprint_dependency_accepts_compact_at_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lakefile.lean").write_text(
                'require VersoBlueprint from git "https://github.com/leanprover/verso-blueprint"@"main"\n',
                encoding="utf-8",
            )
            self.assertEqual(
                find_verso_blueprint_dependency(root),
                ("leanprover/verso-blueprint", "main"),
            )

    def test_find_verso_blueprint_dependency_handles_missing_lakefile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(find_verso_blueprint_dependency(Path(tmp)), (None, None))


if __name__ == "__main__":
    unittest.main()
