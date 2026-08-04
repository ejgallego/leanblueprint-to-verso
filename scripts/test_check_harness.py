#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent


def write_file(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR)


def write_harness_project(
    root: Path,
    *,
    lean_toolchain: str,
    verso_ref: str,
    math_lint_option: str,
    warn_line_length_option: str,
    strict_external_code: bool,
    strict_external_code_option: str,
    lake_strict_external_code: bool,
    formalization_toolchain: str | None = None,
    wrapper_toolchain_override: str | None = None,
) -> None:
    harness_lines = [
        '[harness]',
        'native_warnings = false',
        'docstring_warnings = false',
        f"strict_external_code = {'true' if strict_external_code else 'false'}",
    ]
    if wrapper_toolchain_override is not None:
        harness_lines.append(
            f'wrapper_toolchain_override = "{wrapper_toolchain_override}"'
        )
    write_file(
        root / "verso-harness.toml",
        "\n".join(
            [
                'package_name = "DemoBlueprint"',
                'blueprint_main = "BlueprintMain"',
                'formalization_path = "Demo"',
                'chapter_root = "DemoBlueprint/Chapters"',
                'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                "",
                "[lt]",
                'default_chapters = ["DemoBlueprint/Chapters/SourceChapter.lean"]',
                "",
                *harness_lines,
                "",
            ]
        )
        + "\n",
    )
    write_file(
        root / "lakefile.lean",
        "\n".join(
            [
                "import Lake",
                "open Lake DSL",
                "",
                'require Demo from "./Demo"',
                f'require VersoBlueprint from git "https://github.com/leanprover/verso-blueprint.git" @ "{verso_ref}"',
                "",
                "package DemoBlueprint where",
                "  leanOptions := #[",
                f"    ⟨`{math_lint_option}, true⟩,",
                f"    ⟨`{strict_external_code_option}, {'true' if lake_strict_external_code else 'false'}⟩,",
                f"    ⟨`{warn_line_length_option}, .ofNat 0⟩",
                "  ]",
                "",
                "@[default_target]",
                "lean_lib DemoBlueprint where",
            ]
        )
        + "\n",
    )
    write_file(root / "lean-toolchain", lean_toolchain + "\n")
    write_file(root / "BlueprintMain.lean", "import DemoBlueprint\n")
    write_file(root / "DemoBlueprint.lean", "import DemoBlueprint.TeXPrelude\n")
    write_file(root / "DemoBlueprint" / "TeXPrelude.lean", "import VersoBlueprint\n")
    write_file(
        root / "DemoBlueprint" / "Chapters" / "SourceChapter.lean",
        '#doc (Manual) "Source Chapter" =>\n\nAlpha.\n',
    )
    write_file(
        root / "scripts" / "ci-pages.sh",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root . --warm-cache",
                "lake exe vbp build --output _out/site",
                "python3 tools/verso-harness/scripts/check_generated_site.py --project-root . --site-dir _out/site/html-multi",
                "exit 0",
            ]
        )
        + "\n",
        executable=True,
    )
    write_file(root / "scripts" / "filter_docstring_warnings.py", "print('')\n")
    write_file(
        root / ".github" / "workflows" / "blueprint.yml",
        "name: blueprint\non: workflow_dispatch\njobs: {}\n",
    )
    write_file(
        root / "Demo" / "lean-toolchain",
        (formalization_toolchain or lean_toolchain) + "\n",
    )


def run_check(project_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "check_harness.py"),
            "--project-root",
            str(project_root),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


class CheckHarnessTests(unittest.TestCase):
    def test_check_harness_accepts_explicit_wrapper_toolchain_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.33.0-rc2",
                formalization_toolchain="leanprover/lean4:v4.33.0-rc1",
                wrapper_toolchain_override="leanprover/lean4:v4.33.0-rc2",
                verso_ref="v4.33.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("status: ok", result.stdout)

    def test_check_harness_rejects_wrong_explicit_wrapper_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.33.0-rc1",
                formalization_toolchain="leanprover/lean4:v4.33.0-rc1",
                wrapper_toolchain_override="leanprover/lean4:v4.33.0-rc2",
                verso_ref="v4.33.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("harness.wrapper_toolchain_override", result.stdout)

    def test_check_harness_accepts_weak_policy_for_v428(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.28.0",
                verso_ref="v4.28.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("status: ok", result.stdout)
            self.assertIn("validation boundary: configuration only", result.stdout)
            self.assertIn("remote Pages CI", result.stdout)

    def test_check_harness_accepts_weak_policy_for_v429(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("status: ok", result.stdout)

    def test_check_harness_accepts_weak_policy_for_v431(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.31.0",
                verso_ref="v4.31.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("status: ok", result.stdout)

    def test_check_harness_rejects_v428_strict_external_code_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.28.0",
                verso_ref="v4.28.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=False,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("config:", result.stdout)
            self.assertIn("weak.verso.blueprint.externalCode.strictResolve", result.stdout)
            self.assertIn("harness.strict_external_code", result.stdout)

    def test_check_harness_rejects_ci_pages_deps_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / "scripts" / "ci-pages.sh",
                "#!/usr/bin/env bash\nlake build +BlueprintMain:deps\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("module `:deps` target", result.stdout)

    def test_check_harness_rejects_missing_dependency_cache_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / "scripts" / "ci-pages.sh",
                "#!/usr/bin/env bash\nlake exe vbp build --output _out/site\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("dependency cache guard", result.stdout)

    def test_check_harness_rejects_stale_generated_site_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / "scripts" / "ci-pages.sh",
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "python3 tools/verso-harness/scripts/ensure_dependency_cache.py --project-root . --warm-cache",
                        "lake exe vbp build --output _out/site",
                        "test -f _out/site/html-multi/-verso-data/blueprint-preview-manifest.json",
                    ]
                )
                + "\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("check_generated_site.py", result.stdout)

    def test_check_harness_allows_vbp_base_release_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.30.0-rc2",
                verso_ref="v4.30.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / ".lake" / "packages" / "VersoBlueprint" / "lean-toolchain",
                "leanprover/lean4:v4.30.0\n",
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_check_harness_rejects_ci_pages_executable_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / "scripts" / "ci-pages.sh",
                "#!/usr/bin/env bash\nlake build blueprint-gen\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("must not build the `blueprint-gen` executable", result.stdout)

    def test_check_harness_rejects_legacy_lake_lean_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_project(
                root,
                lean_toolchain="leanprover/lean4:v4.29.0",
                verso_ref="v4.29.0",
                math_lint_option="weak.verso.blueprint.math.lint",
                warn_line_length_option="weak.verso.code.warnLineLength",
                strict_external_code=True,
                strict_external_code_option="weak.verso.blueprint.externalCode.strictResolve",
                lake_strict_external_code=True,
            )
            write_file(
                root / "scripts" / "ci-pages.sh",
                "#!/usr/bin/env bash\nlake lean BlueprintMain.lean -- --run BlueprintMain.lean\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("legacy `lake lean` generator path", result.stdout)


if __name__ == "__main__":
    unittest.main()
