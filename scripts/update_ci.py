#!/usr/bin/env python3

from __future__ import annotations

import argparse
import stat
import sys
from pathlib import Path

from _harnesslib import find_verso_blueprint_dependency, parse_github_repo_slug


TRACKED_FILES = [
    Path("scripts/ci-pages.sh"),
    Path(".github/workflows/blueprint.yml"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh helper-owned CI files in a host repo."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files.",
    )
    parser.add_argument(
        "--pages-workflow-repo",
        default=None,
        help=(
            "Optional override for the reusable workflow repository. By default the helper "
            "uses the VersoBlueprint repository declared in lakefile.lean."
        ),
    )
    parser.add_argument(
        "--pages-workflow-ref",
        default=None,
        help=(
            "Optional override for the reusable workflow ref. By default the helper uses "
            "the VersoBlueprint ref declared in lakefile.lean."
        ),
    )
    return parser.parse_args()


def render_text(text: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def ensure_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def default_pages_workflow_repo() -> str:
    repo = parse_github_repo_slug("https://github.com/leanprover/verso-blueprint.git")
    if repo is None:
        raise SystemExit("internal error: failed to resolve default Pages workflow repo")
    return repo


def main() -> int:
    args = parse_args()
    template_root = Path(__file__).resolve().parents[1] / "templates" / "repo-root"
    project_root = args.project_root.resolve()
    blueprint_repo, blueprint_ref = find_verso_blueprint_dependency(project_root)
    pages_workflow_repo = args.pages_workflow_repo or blueprint_repo or default_pages_workflow_repo()
    pages_workflow_ref = args.pages_workflow_ref or blueprint_ref
    if pages_workflow_ref is None:
        raise SystemExit(
            "could not determine Pages workflow ref from lakefile.lean; "
            "pass --pages-workflow-ref explicitly"
        )
    replacements = {
        "__PAGES_WORKFLOW_REPO__": pages_workflow_repo,
        "__PAGES_WORKFLOW_REF__": pages_workflow_ref,
    }

    changed = 0
    unchanged = 0

    for relative in TRACKED_FILES:
        source = template_root / relative
        target = project_root / relative
        source_text = render_text(source.read_text(encoding="utf-8"), replacements)
        target_text = target.read_text(encoding="utf-8") if target.exists() else None

        if target_text == source_text:
            unchanged += 1
            print(f"unchanged {relative}")
            continue

        changed += 1
        print(f"update    {relative}")
        if args.dry_run:
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_text, encoding="utf-8")
        if target.name == "ci-pages.sh":
            ensure_executable(target)

    print(f"changed: {changed}")
    print(f"unchanged: {unchanged}")
    print(f"pages workflow repo: {pages_workflow_repo}")
    print(f"pages workflow ref: {pages_workflow_ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
