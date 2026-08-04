#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import (  # noqa: E402
    default_verso_blueprint_ref,
    load_config,
    read_verso_blueprint_requirement,
    resolve_project_root,
)


class StatusError(RuntimeError):
    pass


@dataclass
class Section:
    name: str
    facts: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class ManifestPackage:
    url: str | None
    rev: str | None
    input_rev: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repo-level maintenance status for the helper checkout, the vendored "
            "formalization, and the VersoBlueprint dependency."
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Host project root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--helper-root",
        type=Path,
        default=None,
        help=(
            "Helper checkout root. Defaults to the repository that contains this script."
        ),
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip remote freshness checks and report only local consistency.",
    )
    return parser.parse_args()


def run_command(command: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise StatusError(detail)
    return result.stdout.strip()


def short_sha(value: str | None) -> str:
    if value is None:
        return "n/a"
    return value[:12]


def git_output(repo: Path, args: list[str]) -> str:
    return run_command(["git", "-C", str(repo), *args])


def read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def read_verso_blueprint_dependency(project_root: Path) -> tuple[str | None, str | None]:
    return read_verso_blueprint_requirement(project_root)


def choose_remote(repo: Path) -> str | None:
    output = git_output(repo, ["remote"])
    remotes = [line.strip() for line in output.splitlines() if line.strip()]
    if not remotes:
        return None
    return "origin" if "origin" in remotes else remotes[0]


def remote_head(repo: Path, remote_name: str) -> tuple[str | None, str]:
    output = git_output(repo, ["ls-remote", "--symref", remote_name, "HEAD"])
    branch = None
    head_commit = None
    for line in output.splitlines():
        if line.startswith("ref: "):
            ref = line.split()[1]
            if ref.startswith("refs/heads/"):
                branch = ref[len("refs/heads/") :]
        elif line.endswith("\tHEAD"):
            head_commit = line.split("\t", 1)[0]
    if head_commit is None:
        raise StatusError("remote HEAD did not return a commit")
    return branch, head_commit


def resolve_remote_ref(url: str, ref: str) -> str | None:
    queries = [
        f"refs/heads/{ref}",
        f"refs/tags/{ref}",
        ref,
    ]
    for query in queries:
        output = run_command(["git", "ls-remote", url, query])
        entries = []
        for line in output.splitlines():
            if "\t" not in line:
                continue
            sha, name = line.split("\t", 1)
            if sha and name:
                entries.append((name, sha))
        if not entries:
            continue
        for name, sha in entries:
            if name.endswith("^{}"):
                return sha
        return entries[0][1]
    return None


def load_manifest_package(project_root: Path, package_name: str) -> ManifestPackage | None:
    manifest_path = project_root / "lake-manifest.json"
    if not manifest_path.exists():
        return None

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StatusError(f"invalid lake-manifest.json: {exc}") from exc

    packages = data.get("packages")
    if not isinstance(packages, list):
        raise StatusError("invalid lake-manifest.json: missing packages array")

    for package in packages:
        if not isinstance(package, dict):
            continue
        if package.get("name") != package_name:
            continue
        url = package.get("url")
        rev = package.get("rev")
        input_rev = package.get("inputRev")
        return ManifestPackage(
            url=url if isinstance(url, str) and url else None,
            rev=rev if isinstance(rev, str) and rev else None,
            input_rev=input_rev if isinstance(input_rev, str) and input_rev else None,
        )
    return None


def fallback_package_rev(project_root: Path, package_name: str) -> str | None:
    package_root = project_root / ".lake" / "packages" / package_name
    if not package_root.exists():
        return None
    try:
        return git_output(package_root, ["rev-parse", "HEAD"])
    except StatusError:
        return None


def inspect_checkout(name: str, repo: Path, *, offline: bool) -> Section:
    section = Section(name)
    section.facts.append(("path", str(repo)))

    if not repo.exists():
        section.issues.append("path does not exist")
        return section

    try:
        current = git_output(repo, ["rev-parse", "HEAD"])
    except StatusError as exc:
        section.issues.append(f"not a git checkout: {exc}")
        return section

    section.facts.append(("current", short_sha(current)))
    remote_name = choose_remote(repo)
    if remote_name is None:
        section.issues.append("no git remote configured")
        return section

    section.facts.append(("remote", remote_name))
    if offline:
        section.notes.append("remote checks skipped (--offline)")
        return section

    try:
        branch, remote_commit = remote_head(repo, remote_name)
    except StatusError as exc:
        section.issues.append(f"remote query failed: {exc}")
        return section

    remote_label = f"{remote_name}/{branch}" if branch is not None else f"{remote_name}/HEAD"
    section.facts.append(("remote_head", f"{remote_label} {short_sha(remote_commit)}"))
    if current != remote_commit:
        section.issues.append(
            f"update available: current {short_sha(current)} differs from {remote_label} {short_sha(remote_commit)}"
        )
    return section


def inspect_toolchain(
    project_root: Path,
    formalization_root: Path,
    wrapper_toolchain_override: str | None = None,
) -> tuple[Section, str | None, str | None]:
    section = Section("toolchain")
    root_toolchain = read_text(project_root / "lean-toolchain")
    formalization_toolchain = read_text(formalization_root / "lean-toolchain")

    if root_toolchain is None:
        section.issues.append("missing root lean-toolchain")
    else:
        section.facts.append(("root", root_toolchain))

    if formalization_toolchain is None:
        section.issues.append(f"missing upstream lean-toolchain at {formalization_root / 'lean-toolchain'}")
    else:
        section.facts.append(("upstream", formalization_toolchain))

    if wrapper_toolchain_override is not None:
        section.facts.append(("wrapper_override", wrapper_toolchain_override))
        if root_toolchain != wrapper_toolchain_override:
            section.issues.append(
                "root lean-toolchain does not match harness.wrapper_toolchain_override"
            )
        elif formalization_toolchain and root_toolchain != formalization_toolchain:
            section.notes.append("accepted explicit wrapper/formalization toolchain override")
    elif root_toolchain and formalization_toolchain and root_toolchain != formalization_toolchain:
        section.issues.append("root lean-toolchain does not match the vendored formalization")

    source = wrapper_toolchain_override or formalization_toolchain or root_toolchain
    expected_ref = default_verso_blueprint_ref(source) if source is not None else None
    if expected_ref is not None:
        section.facts.append(("expected_verso_ref", expected_ref))
    return section, expected_ref, source


def inspect_verso_blueprint(
    project_root: Path,
    *,
    expected_ref: str | None,
    expected_toolchain: str | None,
    offline: bool,
) -> Section:
    section = Section("verso-blueprint")
    url, declared_ref = read_verso_blueprint_dependency(project_root)

    if url is None or declared_ref is None:
        section.issues.append("could not read VersoBlueprint dependency from lakefile.lean")
        return section

    section.facts.append(("url", url))
    section.facts.append(("lakefile_ref", declared_ref))
    if expected_ref is not None:
        section.facts.append(("expected_ref", expected_ref))
        if declared_ref != expected_ref:
            section.issues.append(
                f"lakefile ref {declared_ref!r} does not match expected {expected_ref!r}"
            )

    manifest_package = None
    try:
        manifest_package = load_manifest_package(project_root, "VersoBlueprint")
    except StatusError as exc:
        section.issues.append(str(exc))

    resolved_rev = None
    if manifest_package is not None:
        if manifest_package.input_rev is not None:
            section.facts.append(("manifest_input_rev", manifest_package.input_rev))
            if manifest_package.input_rev != declared_ref:
                section.issues.append(
                    f"lake-manifest.json inputRev {manifest_package.input_rev!r} does not match lakefile ref {declared_ref!r}"
                )
        resolved_rev = manifest_package.rev
    if resolved_rev is None:
        resolved_rev = fallback_package_rev(project_root, "VersoBlueprint")

    if resolved_rev is None:
        section.issues.append("VersoBlueprint is not resolved in lake-manifest.json or .lake/packages")
    else:
        section.facts.append(("resolved_rev", short_sha(resolved_rev)))

    package_toolchain = read_text(project_root / ".lake" / "packages" / "VersoBlueprint" / "lean-toolchain")
    if package_toolchain is not None:
        section.facts.append(("package_toolchain", package_toolchain))

    if offline:
        section.notes.append("remote checks skipped (--offline)")
        return section

    try:
        remote_rev = resolve_remote_ref(url, declared_ref)
    except StatusError as exc:
        section.issues.append(f"remote query failed: {exc}")
        return section

    if remote_rev is None:
        section.issues.append(f"could not resolve remote ref {declared_ref!r} at {url}")
        return section

    section.facts.append(("remote_ref_rev", short_sha(remote_rev)))
    if resolved_rev is not None and remote_rev != resolved_rev:
        section.issues.append(
            f"update available: resolved rev {short_sha(resolved_rev)} differs from remote {short_sha(remote_rev)}"
        )
    return section


def print_section(section: Section) -> None:
    print(f"{section.name}:")
    print(f"  status: {'ok' if section.ok else 'needs-attention'}")
    for key, value in section.facts:
        print(f"  {key}: {value}")
    for note in section.notes:
        print(f"  note: {note}")
    for issue in section.issues:
        print(f"  issue: {issue}")


def main() -> int:
    args = parse_args()
    project_root = resolve_project_root(args.project_root)
    helper_root = (
        args.helper_root.resolve()
        if args.helper_root is not None
        else Path(__file__).resolve().parents[1]
    )

    try:
        config = load_config(project_root)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    formalization_root = (project_root / config.formalization_path).resolve()
    sections = [
        inspect_checkout("harness", helper_root, offline=args.offline),
        inspect_checkout("upstream", formalization_root, offline=args.offline),
    ]
    toolchain_section, expected_ref, expected_toolchain = inspect_toolchain(
        project_root,
        formalization_root,
        config.wrapper_toolchain_override,
    )
    sections.append(toolchain_section)
    sections.append(
        inspect_verso_blueprint(
            project_root,
            expected_ref=expected_ref,
            expected_toolchain=expected_toolchain,
            offline=args.offline,
        )
    )

    print(f"project root: {project_root}")
    for section in sections:
        print_section(section)

    failing = [section.name for section in sections if not section.ok]
    if failing:
        print(f"summary: needs attention: {', '.join(failing)}")
        return 1

    print("summary: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
