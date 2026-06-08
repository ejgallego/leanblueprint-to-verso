#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import (  # noqa: E402
    CONFIG_FILENAME,
    find_lake_lean_option_bool,
    find_lake_lean_option_nat,
    find_package_name,
    find_verso_blueprint_dependency,
    load_config,
    verso_math_lint_option_name,
    verso_strict_external_code_option_name,
    verso_warn_line_length_option_name,
)


PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")
CI_DEPS_TARGET_PATTERN = re.compile(r"\blake\s+build\s+[^\n|;&]*:deps\b")
CI_EXE_TARGET_PATTERN = re.compile(r"\blake\s+build\s+blueprint-gen\b")
CI_LAKE_BUILD_PATTERN = re.compile(r"\blake\s+build\b")
CI_CACHE_GUARD_PATTERN = re.compile(r"\bensure_dependency_cache\.py\b")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that a host repo has the expected Verso harness files."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    return parser.parse_args()


def unresolved_placeholders(project_root: Path, paths: list[Path]) -> list[Path]:
    bad: list[Path] = []
    for relative in paths:
        path = project_root / relative
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER_PATTERN.search(text):
            bad.append(relative)
    return bad


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()

    missing: list[Path] = []
    mismatches: list[str] = []
    required = [
        Path(CONFIG_FILENAME),
        Path("lakefile.lean"),
        Path("lean-toolchain"),
        Path("scripts/ci-pages.sh"),
        Path("scripts/filter_docstring_warnings.py"),
        Path(".github/workflows/blueprint.yml"),
    ]

    for relative in required:
        if not (project_root / relative).exists():
            missing.append(relative)

    config = None
    if not missing:
        try:
            config = load_config(project_root)
        except SystemExit as exc:
            mismatches.append(str(exc))

    chapter_paths: list[Path] = []
    if config is not None:
        declared_package = find_package_name(project_root)
        if declared_package is None:
            mismatches.append("missing <package declaration in lakefile.lean>")
        elif declared_package != config.package_name:
            mismatches.append(
                f"lakefile package {declared_package!r} does not match {CONFIG_FILENAME} package_name {config.package_name!r}"
            )

        _, option_ref = find_verso_blueprint_dependency(project_root)
        math_lint_option = verso_math_lint_option_name(option_ref)
        strict_external_code_option = verso_strict_external_code_option_name(option_ref)
        warn_line_length_option = verso_warn_line_length_option_name(option_ref)

        math_lint = find_lake_lean_option_bool(project_root, math_lint_option)
        if math_lint is not True:
            mismatches.append(
                f"lakefile.lean must set `{math_lint_option}` to true in package leanOptions"
            )

        warn_line_length = find_lake_lean_option_nat(project_root, warn_line_length_option)
        if warn_line_length != 0:
            mismatches.append(
                f"lakefile.lean must set `{warn_line_length_option}` to `.ofNat 0` in package leanOptions"
            )

        strict_external_code = find_lake_lean_option_bool(
            project_root,
            strict_external_code_option,
        )
        if strict_external_code != config.strict_external_code:
            expected = "true" if config.strict_external_code else "false"
            mismatches.append(
                "lakefile.lean must set "
                f"`{strict_external_code_option}` to {expected} "
                f"to match {CONFIG_FILENAME} harness.strict_external_code"
            )

        root_toolchain_path = project_root / "lean-toolchain"
        formalization_toolchain_path = (
            project_root / config.formalization_path / "lean-toolchain"
        )
        package_toolchain_path = project_root / ".lake" / "packages" / "VersoBlueprint" / "lean-toolchain"
        expected_toolchain: str | None = None
        if root_toolchain_path.exists():
            expected_toolchain = root_toolchain_path.read_text(encoding="utf-8").strip()
        if formalization_toolchain_path.exists():
            formalization_toolchain = formalization_toolchain_path.read_text(encoding="utf-8").strip()
            if expected_toolchain is not None and formalization_toolchain != expected_toolchain:
                mismatches.append(
                    "root lean-toolchain must match the vendored formalization "
                    f"({expected_toolchain!r} != {formalization_toolchain!r})"
                )
            expected_toolchain = formalization_toolchain
        if root_toolchain_path.exists() and package_toolchain_path.exists():
            package_toolchain = package_toolchain_path.read_text(encoding="utf-8").strip()
            if expected_toolchain is not None and package_toolchain != expected_toolchain:
                mismatches.append(
                    "resolved VersoBlueprint lean-toolchain must match the root/formalization "
                    f"toolchain ({package_toolchain!r} != {expected_toolchain!r})"
                )

        for relative in [
            Path(config.formalization_path),
            Path(f"{config.blueprint_main}.lean"),
            Path(f"{config.package_name}.lean"),
            Path(config.package_name) / "TeXPrelude.lean",
        ]:
            if not (project_root / relative).exists():
                missing.append(relative)

        chapter_dir = project_root / config.chapter_root
        if chapter_dir.exists():
            chapter_paths = sorted(
                path.relative_to(project_root)
                for path in chapter_dir.glob("*.lean")
            )

        for relative in [Path(path) for path in config.lt_default_chapters]:
            if not (project_root / relative).exists():
                missing.append(relative)
    placeholder_targets = required.copy()
    if config is not None:
        placeholder_targets.extend(
            [
                Path(f"{config.blueprint_main}.lean"),
                Path(config.formalization_path),
                Path(f"{config.package_name}.lean"),
                Path(config.package_name) / "TeXPrelude.lean",
            ]
        )
    placeholder_targets.extend(chapter_paths)
    placeholder_paths = unresolved_placeholders(project_root, placeholder_targets)

    script_path = project_root / "scripts" / "ci-pages.sh"
    script_executable = (
        script_path.exists() and bool(script_path.stat().st_mode & stat.S_IXUSR)
    )
    if script_path.exists():
        script_text = script_path.read_text(encoding="utf-8")
        build_match = CI_LAKE_BUILD_PATTERN.search(script_text)
        guard_match = CI_CACHE_GUARD_PATTERN.search(script_text)
        if build_match and (guard_match is None or guard_match.start() > build_match.start()):
            mismatches.append(
                "scripts/ci-pages.sh must run the dependency cache guard before `lake build`; "
                "run update_ci.py to refresh helper-owned CI files"
            )
        if CI_DEPS_TARGET_PATTERN.search(script_text):
            mismatches.append(
                "scripts/ci-pages.sh must not build a module `:deps` target; "
                "that target can force Lake to rebuild external dependency packages"
            )
        if CI_EXE_TARGET_PATTERN.search(script_text):
            mismatches.append(
                "scripts/ci-pages.sh must not build the `blueprint-gen` executable; "
                "that target can force Lake to build native artifacts for external dependencies"
            )

    if missing or mismatches or placeholder_paths or not script_executable:
        if missing:
            print("missing:")
            for path in missing:
                print(f"  {path}")
        if mismatches:
            print("config:")
            for mismatch in mismatches:
                print(f"  {mismatch}")
        if placeholder_paths:
            print("unresolved placeholders:")
            for path in placeholder_paths:
                print(f"  {path}")
        if script_path.exists() and not script_executable:
            print("ci-pages.sh is not executable")
        return 1

    print(f"project root: {project_root}")
    print(f"package: {config.package_name}")
    print(f"chapter_root: {config.chapter_root}")
    print("status: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
