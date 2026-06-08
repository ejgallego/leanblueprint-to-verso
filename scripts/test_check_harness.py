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
) -> None:
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
                "[harness]",
                'native_warnings = false',
                'docstring_warnings = false',
                f"strict_external_code = {'true' if strict_external_code else 'false'}",
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
    write_file(root / "Demo" / "lean-toolchain", lean_toolchain + "\n")


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
                "#!/usr/bin/env bash\nlake build +BlueprintMain\n",
                executable=True,
            )
            result = run_check(root)
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("dependency cache guard", result.stdout)

    def test_check_harness_rejects_resolved_vbp_toolchain_mismatch(self) -> None:
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
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("resolved VersoBlueprint lean-toolchain", result.stdout)

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


if __name__ == "__main__":
    unittest.main()
