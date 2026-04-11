#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path

from _harnesslib import (
    default_verso_blueprint_ref,
    parse_github_repo_slug,
    verso_math_lint_option_name,
    verso_strict_external_code_option_name,
    verso_warn_line_length_option_name,
)


PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the starter Verso harness into a host repo."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--formalization-name", required=True)
    parser.add_argument("--formalization-path", required=True)
    parser.add_argument(
        "--tex-source-glob",
        default="./blueprint/src/chapter/*.tex",
        help=(
            "Relative TeX source locator in the host repo. This may be a single "
            "file such as ./blueprint/src/chapter/main.tex or a glob-like path "
            "description such as ./blueprint/src/chapter/*.tex."
        ),
    )
    parser.add_argument(
        "--lean-toolchain",
        default=None,
        help=(
            "Optional override for compatibility work only. By default the helper reads "
            "<formalization-path>/lean-toolchain and uses that exact value."
        ),
    )
    parser.add_argument(
        "--verso-blueprint-ref",
        default=None,
        help=(
            "Optional override for compatibility work only. By default the helper selects "
            "the matching VersoBlueprint branch for the chosen Lean toolchain."
        ),
    )
    parser.add_argument(
        "--pages-workflow-repo",
        default=None,
        help=(
            "Optional override for the reusable workflow repository. By default the helper "
            "uses the VersoBlueprint GitHub repository."
        ),
    )
    parser.add_argument(
        "--pages-workflow-ref",
        default=None,
        help=(
            "Optional override for the reusable workflow ref. By default the helper uses "
            "the same ref chosen for the VersoBlueprint dependency."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files that already exist at the destination.",
    )
    return parser.parse_args()


def validate_identifier(name: str, flag: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(name):
        raise SystemExit(f"{flag} must be a Lean-style identifier, got: {name!r}")


def render_text(text: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        text = text.replace(old, new)
    leftovers = sorted(set(PLACEHOLDER_PATTERN.findall(text)))
    if leftovers:
        raise SystemExit(f"unresolved placeholders in rendered text: {leftovers}")
    return text


def render_path(path: Path, replacements: dict[str, str]) -> Path:
    rendered_parts: list[str] = []
    for part in path.parts:
        rendered = part
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)
        if rendered.endswith(".template"):
            rendered = rendered[: -len(".template")]
        rendered_parts.append(rendered)
    return Path(*rendered_parts)


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def default_pages_workflow_repo() -> str:
    repo = parse_github_repo_slug("https://github.com/leanprover/verso-blueprint.git")
    if repo is None:
        raise SystemExit("internal error: failed to resolve default Pages workflow repo")
    return repo


def read_formalization_toolchain(project_root: Path, formalization_path: str) -> str:
    toolchain_path = project_root / formalization_path / "lean-toolchain"
    if not toolchain_path.exists():
        raise SystemExit(
            f"missing upstream lean-toolchain at {toolchain_path}; the upstream formalization "
            "determines the consumer toolchain"
        )
    value = toolchain_path.read_text(encoding="utf-8").strip()
    if not value:
        raise SystemExit(f"empty upstream lean-toolchain at {toolchain_path}")
    return value


def resolve_harness_versions(args: argparse.Namespace, project_root: Path) -> tuple[str, str]:
    lean_toolchain = args.lean_toolchain or read_formalization_toolchain(
        project_root,
        args.formalization_path,
    )
    verso_blueprint_ref = args.verso_blueprint_ref or default_verso_blueprint_ref(
        lean_toolchain
    )
    return lean_toolchain, verso_blueprint_ref


def main() -> int:
    args = parse_args()
    validate_identifier(args.package_name, "--package-name")
    validate_identifier(args.formalization_name, "--formalization-name")

    helper_root = Path(__file__).resolve().parents[1]
    template_root = helper_root / "templates" / "repo-root"
    project_root = args.project_root.resolve()
    lean_toolchain, verso_blueprint_ref = resolve_harness_versions(args, project_root)
    pages_workflow_repo = args.pages_workflow_repo or default_pages_workflow_repo()
    pages_workflow_ref = args.pages_workflow_ref or verso_blueprint_ref
    math_lint_option = verso_math_lint_option_name(verso_blueprint_ref)
    strict_external_code_option = verso_strict_external_code_option_name(verso_blueprint_ref)
    warn_line_length_option = verso_warn_line_length_option_name(verso_blueprint_ref)

    replacements = {
        "__PACKAGE_NAME__": args.package_name,
        "__PROJECT_TITLE__": args.title,
        "__FORMALIZATION_NAME__": args.formalization_name,
        "__FORMALIZATION_PATH__": args.formalization_path,
        "__TEX_SOURCE_GLOB__": args.tex_source_glob,
        "__LEAN_TOOLCHAIN__": lean_toolchain,
        "__VERSO_BLUEPRINT_REF__": verso_blueprint_ref,
        "__VERSO_MATH_LINT_OPTION__": math_lint_option,
        "__VERSO_STRICT_EXTERNAL_CODE_OPTION__": strict_external_code_option,
        "__VERSO_WARN_LINE_LENGTH_OPTION__": warn_line_length_option,
        "__STRICT_EXTERNAL_CODE__": "true",
        "__PAGES_WORKFLOW_REPO__": pages_workflow_repo,
        "__PAGES_WORKFLOW_REF__": pages_workflow_ref,
    }

    written: list[Path] = []
    skipped: list[Path] = []

    for source in sorted(template_root.rglob("*")):
        if source.is_dir():
            continue
        relative_source = source.relative_to(template_root)
        relative_target = render_path(relative_source, replacements)
        target = project_root / relative_target

        if target.exists() and not args.force:
            skipped.append(relative_target)
            continue

        rendered = render_text(source.read_text(encoding="utf-8"), replacements)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")

        if target.name == "ci-pages.sh":
            ensure_executable(target)

        written.append(relative_target)

    print(f"project root: {project_root}")
    print(f"formalization path: {args.formalization_path}")
    print(f"lean-toolchain: {lean_toolchain}")
    print(f"VersoBlueprint ref: {verso_blueprint_ref}")
    print(f"Pages workflow repo: {pages_workflow_repo}")
    print(f"Pages workflow ref: {pages_workflow_ref}")
    print(f"written: {len(written)}")
    for path in written:
        print(f"  write {path}")
    print(f"skipped: {len(skipped)}")
    for path in skipped:
        print(f"  skip  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
