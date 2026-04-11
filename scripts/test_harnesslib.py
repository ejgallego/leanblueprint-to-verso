#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import (  # noqa: E402
    default_verso_blueprint_ref,
    find_lake_lean_option_bool,
    find_lake_lean_option_nat,
    find_verso_blueprint_dependency,
    parse_github_repo_slug,
    verso_math_lint_option_name,
    verso_strict_external_code_option_name,
    verso_warn_line_length_option_name,
)


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

    def test_default_verso_blueprint_ref_uses_v_release_convention(self) -> None:
        self.assertEqual(
            default_verso_blueprint_ref("leanprover/lean4:v4.28.0"),
            "v4.28.0",
        )
        self.assertEqual(
            default_verso_blueprint_ref("leanprover/lean4:nightly-2026-04-10"),
            "nightly-2026-04-10",
        )

    def test_versioned_verso_option_names_follow_ref_policy(self) -> None:
        self.assertEqual(
            verso_math_lint_option_name("v4.28.0"),
            "weak.verso.blueprint.math.lint",
        )
        self.assertEqual(
            verso_strict_external_code_option_name("lean-v4.28.0"),
            "weak.verso.blueprint.externalCode.strictResolve",
        )
        self.assertEqual(
            verso_warn_line_length_option_name("v4.28.0"),
            "weak.verso.code.warnLineLength",
        )
        self.assertEqual(
            verso_math_lint_option_name("v4.29.0"),
            "weak.verso.blueprint.math.lint",
        )
        self.assertEqual(
            verso_strict_external_code_option_name("v4.29.0"),
            "weak.verso.blueprint.externalCode.strictResolve",
        )
        self.assertEqual(
            verso_warn_line_length_option_name("v4.29.0"),
            "weak.verso.code.warnLineLength",
        )
        self.assertEqual(
            verso_math_lint_option_name("main"),
            "verso.blueprint.math.lint",
        )

    def test_find_lake_lean_option_helpers_read_generated_policy_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lakefile.lean").write_text(
                '\n'.join(
                    [
                        'package DemoBlueprint where',
                        '  leanOptions := #[',
                        '    ⟨`weak.verso.blueprint.math.lint, true⟩,',
                        '    ⟨`weak.verso.blueprint.externalCode.strictResolve, false⟩,',
                        '    ⟨`weak.verso.code.warnLineLength, .ofNat 0⟩',
                        '  ]',
                    ]
                )
                + '\n',
                encoding='utf-8',
            )
            self.assertTrue(find_lake_lean_option_bool(root, "weak.verso.blueprint.math.lint"))
            self.assertFalse(
                find_lake_lean_option_bool(
                    root,
                    "weak.verso.blueprint.externalCode.strictResolve",
                )
            )
            self.assertEqual(find_lake_lean_option_nat(root, "weak.verso.code.warnLineLength"), 0)


if __name__ == "__main__":
    unittest.main()
