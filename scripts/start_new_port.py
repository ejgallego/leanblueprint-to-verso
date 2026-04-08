#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Start a new deterministic Leanblueprint-to-Verso port in an empty or nearly-empty "
            "integration repository."
        )
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--formalization-name", required=True)
    parser.add_argument("--formalization-remote", required=True)
    parser.add_argument("--formalization-path", required=True)
    parser.add_argument(
        "--formalization-branch",
        default=None,
        help="Optional branch name to pass to `git submodule add -b`.",
    )
    parser.add_argument(
        "--tex-source-glob",
        default="./blueprint/src/chapter/*.tex",
        help="Glob-like description of the TeX chapter sources in the upstream repo.",
    )
    parser.add_argument(
        "--lean-toolchain",
        default="leanprover/lean4:v4.28.0",
    )
    parser.add_argument(
        "--verso-blueprint-ref",
        default="lean-v4.28.0",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow the target repo root to already contain canonical helper-managed files.",
    )
    return parser.parse_args()


def run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def ensure_relative_path(value: str, flag: str) -> str:
    if Path(value).is_absolute():
        raise SystemExit(f"{flag} must be a relative path, got: {value!r}")
    return value


def ensure_canonical_start_state(project_root: Path, *, force: bool) -> None:
    project_root.mkdir(parents=True, exist_ok=True)
    allowed = {".git", ".gitmodules", "tools"}
    unexpected = [entry.name for entry in project_root.iterdir() if entry.name not in allowed]
    if unexpected and not force:
        raise SystemExit(
            "project root is not in the canonical start state; unexpected top-level entries: "
            + ", ".join(sorted(unexpected))
        )

    tools_dir = project_root / "tools"
    if tools_dir.exists():
        extras = [entry.name for entry in tools_dir.iterdir() if entry.name != "verso-harness"]
        if extras and not force:
            raise SystemExit(
                "tools/ contains unexpected entries; canonical start only allows tools/verso-harness: "
                + ", ".join(sorted(extras))
            )


def ensure_git_repo(project_root: Path) -> None:
    if not (project_root / ".git").exists():
        run(["git", "init"], cwd=project_root)


def add_formalization_submodule(
    project_root: Path,
    *,
    remote: str,
    path: str,
    branch: str | None,
) -> None:
    target = project_root / path
    if target.exists():
        raise SystemExit(f"formalization path already exists: {target}")

    command = ["git", "-c", "protocol.file.allow=always", "submodule", "add"]
    if branch:
        command.extend(["-b", branch])
    command.extend([remote, path])
    run(command, cwd=project_root)


def run_bootstrap(args: argparse.Namespace, project_root: Path, formalization_path: str) -> None:
    bootstrap_script = Path(__file__).resolve().with_name("bootstrap.py")
    command = [
        sys.executable,
        str(bootstrap_script),
        "--project-root",
        str(project_root),
        "--package-name",
        args.package_name,
        "--title",
        args.title,
        "--formalization-name",
        args.formalization_name,
        "--formalization-path",
        formalization_path,
        "--tex-source-glob",
        args.tex_source_glob,
        "--lean-toolchain",
        args.lean_toolchain,
        "--verso-blueprint-ref",
        args.verso_blueprint_ref,
    ]
    if args.force:
        command.append("--force")
    run(command, cwd=project_root)


def print_next_steps(project_root: Path) -> None:
    print("\nNext steps:")
    print(f"1. Review {project_root / 'verso-harness.toml'} and set lt.default_chapters explicitly.")
    print("2. Run `python3 tools/verso-harness/scripts/check_harness.py --project-root .`.")
    print("3. Copy the host guidance from `tools/verso-harness/snippets/AGENTS.host.md` into `AGENTS.md`.")
    print("4. Start the first LT pass using `references/start-new-port.md`.")


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    formalization_path = ensure_relative_path(args.formalization_path, "--formalization-path")

    ensure_canonical_start_state(project_root, force=args.force)
    ensure_git_repo(project_root)
    add_formalization_submodule(
        project_root,
        remote=args.formalization_remote,
        path=formalization_path,
        branch=args.formalization_branch,
    )
    run_bootstrap(args, project_root, formalization_path)
    print_next_steps(project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
