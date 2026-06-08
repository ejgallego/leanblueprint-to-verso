#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
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


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git_init_repo(path: Path, branch: str) -> None:
    result = run(["git", "init", "--initial-branch", branch], cwd=path)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def git_init_bare(path: Path, branch: str) -> None:
    result = run(["git", "init", "--bare", "--initial-branch", branch, str(path)], cwd=path.parent)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def git_commit_all(repo: Path, message: str) -> str:
    add = run(["git", "add", "."], cwd=repo)
    if add.returncode != 0:
        raise AssertionError(add.stdout + add.stderr)
    commit = run(
        [
            "git",
            "-c",
            "user.name=Codex",
            "-c",
            "user.email=codex@example.com",
            "commit",
            "-m",
            message,
        ],
        cwd=repo,
    )
    if commit.returncode != 0:
        raise AssertionError(commit.stdout + commit.stderr)
    rev = run(["git", "rev-parse", "HEAD"], cwd=repo)
    if rev.returncode != 0:
        raise AssertionError(rev.stdout + rev.stderr)
    return rev.stdout.strip()


def git_push(repo: Path, branch: str) -> None:
    push = run(["git", "push", "-u", "origin", branch], cwd=repo)
    if push.returncode != 0:
        raise AssertionError(push.stdout + push.stderr)


def create_remote_with_checkout(
    root: Path,
    name: str,
    *,
    branch: str,
    initial_files: dict[str, str],
    update_files: dict[str, str] | None = None,
) -> tuple[Path, Path, Path, str, str]:
    remote = root / f"{name}-remote.git"
    git_init_bare(remote, branch)

    source = root / f"{name}-src"
    source.mkdir()
    git_init_repo(source, branch)
    for relative, text in initial_files.items():
        write_file(source / relative, text)
    first_commit = git_commit_all(source, "initial")
    remote_add = run(["git", "remote", "add", "origin", str(remote)], cwd=source)
    if remote_add.returncode != 0:
        raise AssertionError(remote_add.stdout + remote_add.stderr)
    git_push(source, branch)

    checkout = root / f"{name}-checkout"
    clone = run(["git", "clone", str(remote), str(checkout)], cwd=root)
    if clone.returncode != 0:
        raise AssertionError(clone.stdout + clone.stderr)

    latest_commit = first_commit
    if update_files:
        for relative, text in update_files.items():
            write_file(source / relative, text)
        latest_commit = git_commit_all(source, "update")
        git_push(source, branch)

    return remote, source, checkout, first_commit, latest_commit


def write_host_project(
    project_root: Path,
    *,
    formalization_path: str,
    lean_toolchain: str,
    verso_url: str,
    verso_ref: str,
    verso_rev: str | None,
    package_toolchain: str | None = None,
    compact_at_syntax: bool = False,
) -> None:
    write_file(
        project_root / "verso-harness.toml",
        "\n".join(
            [
                'package_name = "DemoBlueprint"',
                'blueprint_main = "BlueprintMain"',
                f'formalization_path = "{formalization_path}"',
                'chapter_root = "DemoBlueprint/Chapters"',
                'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                "",
                "[lt]",
                'default_chapters = ["DemoBlueprint/Chapters/SourceChapter.lean"]',
                "",
            ]
        )
        + "\n",
    )
    verso_requirement = (
        f'require VersoBlueprint from git "{verso_url}"@"{verso_ref}"'
        if compact_at_syntax
        else f'require VersoBlueprint from git "{verso_url}" @ "{verso_ref}"'
    )
    write_file(project_root / "lean-toolchain", lean_toolchain + "\n")
    write_file(
        project_root / "lakefile.lean",
        "\n".join(
            [
                "import Lake",
                "open Lake DSL",
                "",
                f'require Demo from "./{formalization_path}"',
                verso_requirement,
                "",
                "package DemoBlueprint where",
            ]
        )
        + "\n",
    )
    write_file(project_root / "BlueprintMain.lean", "import DemoBlueprint\n")
    write_file(project_root / "DemoBlueprint.lean", "import DemoBlueprint.TeXPrelude\n")
    write_file(project_root / "DemoBlueprint" / "TeXPrelude.lean", "import VersoBlueprint\n")
    write_file(
        project_root / "DemoBlueprint" / "Chapters" / "SourceChapter.lean",
        "/-- source chapter -/\ndef demoChapter : Nat := 0\n",
    )
    write_file(project_root / "scripts" / "ci-pages.sh", "#!/usr/bin/env bash\n")
    write_file(project_root / ".github" / "workflows" / "blueprint.yml", "name: demo\n")

    if verso_rev is not None:
        manifest = {
            "version": "1.1.0",
            "packagesDir": ".lake/packages",
            "packages": [
                {
                    "url": verso_url,
                    "type": "git",
                    "scope": "",
                    "rev": verso_rev,
                    "name": "VersoBlueprint",
                    "manifestFile": "lake-manifest.json",
                    "inputRev": verso_ref,
                    "inherited": False,
                    "configFile": "lakefile.lean",
                }
            ],
            "name": "DemoBlueprint",
            "lakeDir": ".lake",
        }
        write_file(project_root / "lake-manifest.json", json.dumps(manifest, indent=1) + "\n")
    if package_toolchain is not None:
        write_file(
            project_root / ".lake" / "packages" / "VersoBlueprint" / "lean-toolchain",
            package_toolchain + "\n",
        )


class StatusHarnessTests(unittest.TestCase):
    def test_status_harness_reports_updates_for_helper_upstream_and_verso(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper_remote, _, helper_checkout, _, helper_latest = create_remote_with_checkout(
                root,
                "helper",
                branch="main",
                initial_files={"README.md": "helper\n"},
                update_files={"README.md": "helper v2\n"},
            )
            _, _, formalization_checkout, _, _ = create_remote_with_checkout(
                root,
                "formalization",
                branch="main",
                initial_files={"lean-toolchain": "leanprover/lean4:v4.28.0\n"},
                update_files={"README.md": "new upstream change\n"},
            )
            verso_remote, verso_source, _, verso_first, verso_latest = create_remote_with_checkout(
                root,
                "verso",
                branch="v4.28.0",
                initial_files={"README.md": "verso\n"},
                update_files={"README.md": "verso v2\n"},
            )

            self.assertNotEqual(verso_first, verso_latest)
            self.assertTrue(helper_remote.exists())
            self.assertTrue(helper_latest)

            project_root = root / "project"
            write_host_project(
                project_root,
                formalization_path="Formalization",
                lean_toolchain="leanprover/lean4:v4.28.0",
                verso_url=str(verso_remote),
                verso_ref="v4.28.0",
                verso_rev=verso_first,
            )

            shutil.copytree(formalization_checkout, project_root / "Formalization")

            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_harness.py"),
                    "--project-root",
                    str(project_root),
                    "--helper-root",
                    str(helper_checkout),
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("harness:", result.stdout)
            self.assertIn("upstream:", result.stdout)
            self.assertIn("toolchain:", result.stdout)
            self.assertIn("verso-blueprint:", result.stdout)
            self.assertIn("summary: needs attention: harness, upstream, verso-blueprint", result.stdout)
            self.assertIn("update available: current", result.stdout)
            self.assertIn(f"remote_ref_rev: {verso_latest[:12]}", result.stdout)

            helper_checkout_head = run(["git", "rev-parse", "HEAD"], cwd=helper_checkout)
            self.assertEqual(helper_checkout_head.returncode, 0, msg=helper_checkout_head.stdout + helper_checkout_head.stderr)
            self.assertNotEqual(helper_checkout_head.stdout.strip(), helper_latest)

            verso_source_head = run(["git", "rev-parse", "HEAD"], cwd=verso_source)
            self.assertEqual(verso_source_head.returncode, 0, msg=verso_source_head.stdout + verso_source_head.stderr)
            self.assertEqual(verso_source_head.stdout.strip(), verso_latest)

    def test_status_harness_returns_ok_when_everything_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, helper_checkout, _, _ = create_remote_with_checkout(
                root,
                "helper",
                branch="main",
                initial_files={"README.md": "helper\n"},
            )
            verso_remote, _, _, verso_rev, _ = create_remote_with_checkout(
                root,
                "verso",
                branch="v4.28.0",
                initial_files={"README.md": "verso\n"},
            )
            _, _, formalization_checkout, _, _ = create_remote_with_checkout(
                root,
                "formalization",
                branch="main",
                initial_files={"lean-toolchain": "leanprover/lean4:v4.28.0\n"},
            )

            project_root = root / "project"
            write_host_project(
                project_root,
                formalization_path="Formalization",
                lean_toolchain="leanprover/lean4:v4.28.0",
                verso_url=str(verso_remote),
                verso_ref="v4.28.0",
                verso_rev=verso_rev,
            )
            shutil.copytree(formalization_checkout, project_root / "Formalization")

            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_harness.py"),
                    "--project-root",
                    str(project_root),
                    "--helper-root",
                    str(helper_checkout),
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("summary: ok", result.stdout)
            self.assertNotIn("needs attention", result.stdout)

    def test_status_harness_accepts_base_verso_ref_for_lean_prerelease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, helper_checkout, _, _ = create_remote_with_checkout(
                root,
                "helper",
                branch="main",
                initial_files={"README.md": "helper\n"},
            )
            verso_remote, _, _, verso_rev, _ = create_remote_with_checkout(
                root,
                "verso",
                branch="v4.30.0",
                initial_files={"README.md": "verso\n"},
            )
            _, _, formalization_checkout, _, _ = create_remote_with_checkout(
                root,
                "formalization",
                branch="main",
                initial_files={"lean-toolchain": "leanprover/lean4:v4.30.0-rc2\n"},
            )

            project_root = root / "project"
            write_host_project(
                project_root,
                formalization_path="Formalization",
                lean_toolchain="leanprover/lean4:v4.30.0-rc2",
                verso_url=str(verso_remote),
                verso_ref="v4.30.0",
                verso_rev=verso_rev,
                package_toolchain="leanprover/lean4:v4.30.0-rc2",
            )
            shutil.copytree(formalization_checkout, project_root / "Formalization")

            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_harness.py"),
                    "--project-root",
                    str(project_root),
                    "--helper-root",
                    str(helper_checkout),
                    "--offline",
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("expected_verso_ref: v4.30.0", result.stdout)
            self.assertIn("expected_ref: v4.30.0", result.stdout)
            self.assertIn("package_toolchain: leanprover/lean4:v4.30.0-rc2", result.stdout)
            self.assertIn("summary: ok", result.stdout)

    def test_status_harness_rejects_resolved_vbp_toolchain_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, helper_checkout, _, _ = create_remote_with_checkout(
                root,
                "helper",
                branch="main",
                initial_files={"README.md": "helper\n"},
            )
            verso_remote, _, _, verso_rev, _ = create_remote_with_checkout(
                root,
                "verso",
                branch="v4.30.0",
                initial_files={"README.md": "verso\n"},
            )
            _, _, formalization_checkout, _, _ = create_remote_with_checkout(
                root,
                "formalization",
                branch="main",
                initial_files={"lean-toolchain": "leanprover/lean4:v4.30.0-rc2\n"},
            )

            project_root = root / "project"
            write_host_project(
                project_root,
                formalization_path="Formalization",
                lean_toolchain="leanprover/lean4:v4.30.0-rc2",
                verso_url=str(verso_remote),
                verso_ref="v4.30.0",
                verso_rev=verso_rev,
                package_toolchain="leanprover/lean4:v4.30.0",
            )
            shutil.copytree(formalization_checkout, project_root / "Formalization")

            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_harness.py"),
                    "--project-root",
                    str(project_root),
                    "--helper-root",
                    str(helper_checkout),
                    "--offline",
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout + result.stderr)
            self.assertIn("resolved VersoBlueprint lean-toolchain", result.stdout)
            self.assertIn("summary: needs attention: verso-blueprint", result.stdout)

    def test_status_harness_accepts_compact_at_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, _, helper_checkout, _, _ = create_remote_with_checkout(
                root,
                "helper",
                branch="main",
                initial_files={"README.md": "helper\n"},
            )
            verso_remote, _, _, verso_rev, _ = create_remote_with_checkout(
                root,
                "verso",
                branch="v4.28.0",
                initial_files={"README.md": "verso\n"},
            )
            _, _, formalization_checkout, _, _ = create_remote_with_checkout(
                root,
                "formalization",
                branch="main",
                initial_files={"lean-toolchain": "leanprover/lean4:v4.28.0\n"},
            )

            project_root = root / "project"
            write_host_project(
                project_root,
                formalization_path="Formalization",
                lean_toolchain="leanprover/lean4:v4.28.0",
                verso_url=str(verso_remote),
                verso_ref="v4.28.0",
                verso_rev=verso_rev,
                compact_at_syntax=True,
            )
            shutil.copytree(formalization_checkout, project_root / "Formalization")

            result = run(
                [
                    sys.executable,
                    str(SCRIPT_DIR / "status_harness.py"),
                    "--project-root",
                    str(project_root),
                    "--helper-root",
                    str(helper_checkout),
                    "--offline",
                ],
                cwd=ROOT,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("summary: ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
