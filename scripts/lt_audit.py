#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
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

WARNING_WITH_POSITION_PATTERN = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+):(?P<column>\d+):\s+warning:\s*(?P<message>.*)$"
)
WARNING_WITH_PATH_PATTERN = re.compile(
    r"^(?P<path>.+?):\s+warning:\s*(?P<message>.*)$"
)
WARNING_WITHOUT_PATH_PATTERN = re.compile(r"^warning:\s*(?P<message>.*)$")
WARNING_SUMMARY_SAMPLE_LIMIT = 3


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


@dataclass(frozen=True)
class NativeWarningRecord:
    line: str
    raw_path: str | None
    owner: str


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


def filtered_output_lines(text: str, skip_lines: set[str] | None = None) -> list[str]:
    if not text:
        return []
    if not skip_lines:
        return text.splitlines()
    return [line for line in text.splitlines() if line.strip() not in skip_lines]


def print_step(
    result: StepResult,
    *,
    ok_override: bool | None = None,
    skip_lines: set[str] | None = None,
) -> None:
    ok = result.ok if ok_override is None else ok_override
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {result.name}")
    print(f"    $ {' '.join(result.command)}")
    for line in filtered_output_lines(result.stdout, skip_lines):
        print(f"    {line}")
    for line in filtered_output_lines(result.stderr, skip_lines):
        print(f"    stderr: {line}")


def chapter_build_command(module: str) -> list[str]:
    return ["nice", "lake", "build", module]


def effective_native_warnings(config_default: bool, cli_override: bool | None) -> bool:
    return config_default if cli_override is None else cli_override


def parse_warning_line(line: str) -> tuple[str | None, str] | None:
    stripped = line.strip()
    if not stripped:
        return None
    for pattern in (
        WARNING_WITH_POSITION_PATTERN,
        WARNING_WITH_PATH_PATTERN,
        WARNING_WITHOUT_PATH_PATTERN,
    ):
        match = pattern.match(stripped)
        if match is not None:
            return match.groupdict().get("path"), stripped
    return None


def classify_warning_owner(
    project_root: Path,
    formalization_path: str,
    raw_path: str | None,
) -> str:
    if raw_path is None:
        return "consumer"

    project_root_resolved = project_root.resolve()
    formalization_root = (project_root / formalization_path).resolve()
    path = Path(raw_path)
    resolved_candidates = (
        [path.resolve()]
        if path.is_absolute()
        else [
            (project_root_resolved / path).resolve(),
            (formalization_root / path).resolve(),
        ]
    )

    def classify_resolved(resolved: Path) -> str:
        try:
            relative = resolved.relative_to(project_root_resolved)
        except ValueError:
            return "external"

        if len(relative.parts) >= 2 and relative.parts[0] == ".lake" and relative.parts[1] == "packages":
            return "external"

        try:
            resolved.relative_to(formalization_root)
        except ValueError:
            return "consumer"
        return "upstream"

    if path.is_absolute():
        return classify_resolved(resolved_candidates[0])

    fallback_owner = "consumer"
    for resolved in resolved_candidates:
        owner = classify_resolved(resolved)
        if resolved.exists():
            return owner
        if owner == "external":
            fallback_owner = "external"

    return fallback_owner


def collect_native_warning_records(
    project_root: Path,
    formalization_path: str,
    result: StepResult,
) -> list[NativeWarningRecord]:
    records: list[NativeWarningRecord] = []
    seen_lines: set[str] = set()
    for text in (result.stdout, result.stderr):
        for line in text.splitlines():
            parsed = parse_warning_line(line)
            if parsed is None:
                continue
            raw_path, rendered_line = parsed
            if rendered_line in seen_lines:
                continue
            seen_lines.add(rendered_line)
            records.append(
                NativeWarningRecord(
                    line=rendered_line,
                    raw_path=raw_path,
                    owner=classify_warning_owner(project_root, formalization_path, raw_path),
                )
            )
    return records


def warning_owner_groups(records: list[NativeWarningRecord]) -> dict[str, list[NativeWarningRecord]]:
    groups = {
        "consumer": [],
        "upstream": [],
        "external": [],
    }
    for record in records:
        groups.setdefault(record.owner, []).append(record)
    return groups


def warning_record_is_failing(record: NativeWarningRecord, scope: str) -> bool:
    return scope == "all" or record.owner == "consumer"


def native_warning_check_ok(
    result: StepResult,
    records: list[NativeWarningRecord],
    scope: str,
) -> bool:
    return result.ok and all(not warning_record_is_failing(record, scope) for record in records)


def print_native_warning_summary(records: list[NativeWarningRecord], scope: str) -> None:
    if not records:
        return

    groups = warning_owner_groups(records)
    failing = sum(1 for record in records if warning_record_is_failing(record, scope))
    print(
        "    native warning summary: "
        f"{len(records)} total, {failing} failing under {scope} scope"
    )

    labels = (
        ("consumer", "consumer-owned"),
        ("upstream", "upstream-transitive"),
        ("external", "external-dependency"),
    )
    for owner, label in labels:
        owner_records = groups[owner]
        if not owner_records:
            continue
        outcome = "failing" if warning_record_is_failing(owner_records[0], scope) else "reported only"
        print(f"      {label}: {len(owner_records)} ({outcome})")
        for record in owner_records[:WARNING_SUMMARY_SAMPLE_LIMIT]:
            print(f"        {record.line}")
        omitted = len(owner_records) - WARNING_SUMMARY_SAMPLE_LIMIT
        if omitted > 0:
            print(f"        ... {omitted} more")


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
            "Run the focused chapter build with native warning classification enabled."
        ),
    )
    native_warning_group.add_argument(
        "--no-native-warnings",
        dest="native_warnings",
        action="store_false",
        help="Do not fail the chapter build on native warning logs, even if enabled in verso-harness.toml.",
    )
    parser.add_argument(
        "--native-warnings-scope",
        choices=("consumer", "all"),
        default="consumer",
        help=(
            "When native warning checks are enabled, fail on consumer-owned warnings only "
            "(default) or on all warnings including vendored-formalization and external "
            "dependency warnings."
        ),
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
                    + (
                        f" + native warning check ({args.native_warnings_scope} scope)"
                        if native_warnings
                        else ""
                    ),
                    chapter_build_command(module),
                )
                warning_records = (
                    collect_native_warning_records(
                        project_root,
                        config.formalization_path,
                        build_result,
                    )
                    if native_warnings
                    else []
                )
                build_ok = native_warning_check_ok(
                    build_result,
                    warning_records,
                    args.native_warnings_scope,
                )
                skip_warning_lines = {record.line for record in warning_records} if warning_records else None
                print_step(build_result, ok_override=build_ok, skip_lines=skip_warning_lines)
                print_native_warning_summary(warning_records, args.native_warnings_scope)
                overall_ok &= build_ok

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
