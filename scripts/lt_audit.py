#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import (  # noqa: E402
    lean_file_to_module,
    load_config,
    resolve_chapter_paths,
    resolve_project_root,
)


@dataclass
class StepResult:
    name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_step(project_root: Path, name: str, command: list[str]) -> StepResult:
    result = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return StepResult(
        name=name,
        command=command,
        returncode=result.returncode,
        stdout=result.stdout.strip(),
        stderr=result.stderr.strip(),
    )


def print_step(result: StepResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"  [{status}] {result.name}")
    print(f"    $ {' '.join(result.command)}")
    if result.stdout:
        for line in result.stdout.splitlines():
            print(f"    {line}")
    if result.stderr:
        for line in result.stderr.splitlines():
            print(f"    stderr: {line}")


def chapter_build_command(module: str, *, native_warnings: bool) -> list[str]:
    command = ["nice", "lake"]
    if native_warnings:
        command.append("--wfail")
    command.extend(["build", module])
    return command


def effective_native_warnings(config_default: bool, cli_override: bool | None) -> bool:
    return config_default if cli_override is None else cli_override


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the LT audit stack for one or more chapter files: source-pair check, "
            "similarity report, optional node-kind and math checks, chapter build, and "
            "optionally the pages smoke test."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Lean chapter files to audit. Defaults to the configured lt.default_chapters.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Maximum number of low-similarity blocks to show per file.",
    )
    parser.add_argument(
        "--warn-below",
        type=float,
        default=0.70,
        help="Similarity warning threshold to pass through to check_lt_similarity.py.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip `lake build` for the individual chapter modules.",
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="Also run the full pages smoke test at the end.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Pass through verbose per-block LT similarity output instead of the summary view.",
    )
    parser.add_argument(
        "--node-kinds",
        action="store_true",
        help="Also run the configured graph-visible node-kind checker on each touched chapter.",
    )
    parser.add_argument(
        "--math-sanity",
        action="store_true",
        help="Also run the conservative Verso math-delimiter checker on each touched chapter.",
    )
    native_warning_group = parser.add_mutually_exclusive_group()
    native_warning_group.add_argument(
        "--native-warnings",
        dest="native_warnings",
        action="store_true",
        help=(
            "Fail the chapter build if Lean, Verso, or VersoBlueprint warnings are logged "
            "during elaboration."
        ),
    )
    native_warning_group.add_argument(
        "--no-native-warnings",
        dest="native_warnings",
        action="store_false",
        help="Do not fail the chapter build on native warning logs, even if enabled in verso-harness.toml.",
    )
    parser.set_defaults(native_warnings=None)
    args = parser.parse_args()

    project_root = resolve_project_root(args.project_root)
    config = load_config(project_root)
    paths = resolve_chapter_paths(project_root, args.paths)
    native_warnings = effective_native_warnings(config.native_warnings, args.native_warnings)

    if not paths:
        print("no chapter files selected for LT audit", file=sys.stderr)
        return 2

    overall_ok = True
    source_pair_script = str(SCRIPT_DIR / "check_lt_source_pairs.py")
    similarity_script = str(SCRIPT_DIR / "check_lt_similarity.py")
    node_kind_script = str(SCRIPT_DIR / "check_blueprint_node_kinds.py")
    math_script = str(SCRIPT_DIR / "check_verso_math_delimiters.py")

    for path in paths:
        print(f"\n== {path}")

        pair_result = run_step(
            project_root,
            "LT source-pair audit",
            [sys.executable, source_pair_script, "--project-root", str(project_root), str(path)],
        )
        print_step(pair_result)
        overall_ok &= pair_result.ok

        similarity_command = [
            sys.executable,
            similarity_script,
            "--project-root",
            str(project_root),
            str(path),
            "--top",
            str(args.top),
            "--warn-below",
            str(args.warn_below),
        ]
        if args.verbose:
            similarity_command.append("--verbose")

        similarity_result = run_step(
            project_root,
            "LT similarity report",
            similarity_command,
        )
        print_step(similarity_result)
        overall_ok &= similarity_result.ok

        if args.node_kinds:
            node_kind_result = run_step(
                project_root,
                "node kind check",
                [sys.executable, node_kind_script, "--project-root", str(project_root), str(path)],
            )
            print_step(node_kind_result)
            overall_ok &= node_kind_result.ok

        if args.math_sanity:
            math_result = run_step(
                project_root,
                "math delimiter check",
                [sys.executable, math_script, "--project-root", str(project_root), str(path)],
            )
            print_step(math_result)
            overall_ok &= math_result.ok

        if not args.no_build:
            module = lean_file_to_module(project_root, path)
            if module is None:
                print("  [SKIP] chapter build")
                print("    could not infer a Lake module name from the file path")
            else:
                build_result = run_step(
                    project_root,
                    "chapter build"
                    + (" + native warning check" if native_warnings else ""),
                    chapter_build_command(module, native_warnings=native_warnings),
                )
                print_step(build_result)
                overall_ok &= build_result.ok

    if args.pages:
        print("\n== pages")
        pages_result = run_step(
            project_root,
            "pages smoke test",
            ["bash", "./scripts/ci-pages.sh"],
        )
        print_step(pages_result)
        overall_ok &= pages_result.ok

    print(f"\nOverall: {'OK' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
