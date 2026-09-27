#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _harnesslib import load_config  # noqa: E402


CACHE_GET_COMMAND = ("lake", "exe", "cache", "get")
GUARDED_MODULE_ROOTS = {
    "mathlib": ("Mathlib",),
}
REQUIRED_ARTIFACT_SUFFIXES = (".olean", ".trace", ".olean.hash")
CACHED_LEAN_ARTIFACT_SUFFIXES = (
    ".olean.private",
    ".olean.server",
    ".olean",
    ".ilean",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Warm dependency build caches and refuse to continue when guarded "
            "dependencies would be rebuilt by Lake."
        )
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument(
        "--warm-cache",
        action="store_true",
        help="Run `lake exe cache get` before checking artifacts.",
    )
    parser.add_argument(
        "--max-missing-mathlib-modules",
        type=nonnegative_int,
        default=0,
        metavar="N",
        help=(
            "Allow up to N non-umbrella Mathlib modules with no cached artifacts. "
            "Partial artifact sets and Mathlib.lean are always rejected; default: 0."
        ),
    )
    return parser.parse_args()


def nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def module_source_files(package_dir: Path, module_roots: tuple[str, ...]) -> list[Path]:
    sources: set[Path] = set()
    for module_root in module_roots:
        module_directory = package_dir / module_root
        if module_directory.is_dir():
            sources.update(path for path in module_directory.rglob("*.lean") if path.is_file())
        module_file = package_dir / f"{module_root}.lean"
        if module_file.is_file():
            sources.add(module_file)
    return sorted(sources)


def module_artifact_gaps(
    package_dir: Path,
    sources: list[Path],
) -> tuple[set[str], dict[str, tuple[str, ...]]]:
    """Return fully and partially missing modules keyed by Lean module name."""
    build_root = package_dir / ".lake" / "build" / "lib" / "lean"
    fully_missing: set[str] = set()
    partially_missing: dict[str, tuple[str, ...]] = {}
    for source in sources:
        module_name = ".".join(source.relative_to(package_dir).with_suffix("").parts)
        artifact_base = build_root / source.relative_to(package_dir)
        missing_suffixes = tuple(
            suffix
            for suffix in REQUIRED_ARTIFACT_SUFFIXES
            if not artifact_base.with_suffix(suffix).is_file()
        )
        if not missing_suffixes:
            continue
        if len(missing_suffixes) == len(REQUIRED_ARTIFACT_SUFFIXES):
            fully_missing.add(module_name)
        else:
            partially_missing[module_name] = missing_suffixes
    return fully_missing, partially_missing


def read_manifest_package_names(project_root: Path) -> set[str]:
    manifest_path = project_root / "lake-manifest.json"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"missing {manifest_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {manifest_path}: {exc}")
    packages = data.get("packages")
    if not isinstance(packages, list):
        raise SystemExit(f"invalid Lake manifest format in {manifest_path}: missing packages list")
    names: set[str] = set()
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def read_toolchain(path: Path) -> str | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def read_formalization_toolchain(project_root: Path) -> str | None:
    config = load_config(project_root)
    return read_toolchain(project_root / config.formalization_path / "lean-toolchain")


def selected_project_toolchain(project_root: Path) -> str | None:
    return read_formalization_toolchain(project_root) or read_toolchain(
        project_root / "lean-toolchain"
    )


def sync_toolchain_file(path: Path, selected_toolchain: str) -> bool:
    if read_toolchain(path) == selected_toolchain:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(selected_toolchain + "\n", encoding="utf-8")
    return True


def sync_project_toolchain_selection(project_root: Path) -> list[Path]:
    selected_toolchain = selected_project_toolchain(project_root)
    if selected_toolchain is None:
        return []

    changed: list[Path] = []
    root_toolchain_path = project_root / "lean-toolchain"
    if sync_toolchain_file(root_toolchain_path, selected_toolchain):
        changed.append(root_toolchain_path)

    return changed


def relative_to_project(path: Path, project_root: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def dependency_artifact_report(
    project_root: Path,
    max_missing_mathlib_modules: int = 0,
) -> tuple[list[str], list[str]]:
    package_names = read_manifest_package_names(project_root)
    gaps: list[str] = []
    warnings: list[str] = []
    for package_name, module_roots in GUARDED_MODULE_ROOTS.items():
        if package_name not in package_names:
            continue
        package_dir = project_root / ".lake" / "packages" / package_name
        if not package_dir.exists():
            gaps.append(
                f"{package_name}: missing checkout at {relative_to_project(package_dir, project_root)}"
            )
            continue
        sources = module_source_files(package_dir, module_roots)
        source_count = len(sources)
        if source_count == 0:
            gaps.append(f"{package_name}: no source modules found")
            continue
        fully_missing, partially_missing = module_artifact_gaps(package_dir, sources)
        if not fully_missing and not partially_missing:
            continue
        missing_artifacts = []
        build_root = package_dir / ".lake" / "build" / "lib" / "lean"
        for suffix in REQUIRED_ARTIFACT_SUFFIXES:
            present_count = sum(
                1
                for source in sources
                if (build_root / source.relative_to(package_dir))
                .with_suffix(suffix)
                .is_file()
            )
            if present_count < source_count:
                missing_artifacts.append(f"{suffix} {present_count}/{source_count}")
        details: list[str] = []
        if fully_missing:
            details.append(f"no artifacts: {', '.join(sorted(fully_missing))}")
        if partially_missing:
            partial_details = ", ".join(
                f"{module} ({'/'.join(suffixes)})"
                for module, suffixes in sorted(partially_missing.items())
            )
            details.append(f"partial artifacts: {partial_details}")
        detail_text = f"; {'; '.join(details)}" if details else ""
        if (
            package_name == "mathlib"
            and fully_missing
            and not partially_missing
            and "Mathlib" not in fully_missing
            and len(fully_missing) <= max_missing_mathlib_modules
        ):
            warnings.append(
                f"mathlib: tolerating missing cache artifacts for {len(fully_missing)} "
                f"module(s): {', '.join(sorted(fully_missing))}"
            )
        else:
            gaps.append(
                f"{package_name}: cached artifacts incomplete "
                f"({', '.join(missing_artifacts)}){detail_text}"
            )
    return gaps, warnings


def dependency_artifact_gaps(
    project_root: Path,
    max_missing_mathlib_modules: int = 0,
) -> list[str]:
    gaps, _warnings = dependency_artifact_report(
        project_root,
        max_missing_mathlib_modules=max_missing_mathlib_modules,
    )
    return gaps


def lake_cache_artifacts_dir() -> Path | None:
    candidates: list[str] = []
    lake_path = shutil.which("lake")
    if lake_path is not None:
        candidates.append(lake_path)
    try:
        elan_result = subprocess.run(
            ["elan", "which", "lake"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        elan_result = None
    if elan_result is not None and elan_result.returncode == 0:
        resolved = elan_result.stdout.strip()
        if resolved:
            candidates.append(resolved)

    for candidate in candidates:
        artifact_dir = artifact_dir_for_lake_path(Path(candidate))
        if artifact_dir is not None:
            return artifact_dir
    return None


def artifact_dir_for_lake_path(lake_path: Path) -> Path | None:
    try:
        toolchain_root = Path(lake_path).resolve().parents[1]
    except IndexError:
        return None
    artifact_dir = toolchain_root / "lake" / "cache" / "artifacts"
    return artifact_dir if artifact_dir.exists() else None


def trace_output_artifacts(trace_path: Path) -> list[str]:
    try:
        data = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    outputs = data.get("outputs")
    if not isinstance(outputs, dict):
        return []
    artifacts: list[str] = []
    for value in outputs.values():
        if isinstance(value, str):
            artifacts.append(value)
        elif isinstance(value, list):
            artifacts.extend(item for item in value if isinstance(item, str))
    return artifacts


def local_artifact_path(trace_path: Path, cached_artifact_name: str) -> Path | None:
    for suffix in CACHED_LEAN_ARTIFACT_SUFFIXES:
        if cached_artifact_name.endswith(suffix):
            return trace_path.with_suffix(suffix)
    return None


def link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def materialize_cached_lean_artifacts(
    project_root: Path,
    cache_artifacts_dir: Path | None = None,
) -> list[Path]:
    """Restore missing dependency Lean artifacts from Lake's content cache."""
    cache_dir = (
        cache_artifacts_dir
        if cache_artifacts_dir is not None
        else lake_cache_artifacts_dir()
    )
    if cache_dir is None or not cache_dir.exists():
        return []

    packages_root = project_root / ".lake" / "packages"
    if not packages_root.exists():
        return []

    restored: list[Path] = []
    for trace_path in packages_root.glob("*/.lake/build/lib/lean/**/*.trace"):
        for artifact_name in trace_output_artifacts(trace_path):
            target = local_artifact_path(trace_path, artifact_name)
            if target is None or target.exists():
                continue
            source = cache_dir / artifact_name
            if not source.is_file():
                continue
            link_or_copy(source, target)
            restored.append(target)
    return restored


def warm_cache(project_root: Path) -> int:
    print(f"[dependency-cache] {' '.join(CACHE_GET_COMMAND)}", flush=True)
    return subprocess.run(list(CACHE_GET_COMMAND), cwd=project_root, check=False).returncode


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    for path in sync_project_toolchain_selection(project_root):
        print(f"[dependency-cache] selected Lean toolchain in {relative_to_project(path, project_root)}")
    cache_status = 0
    if args.warm_cache:
        cache_status = warm_cache(project_root)
        for path in sync_project_toolchain_selection(project_root):
            print(f"[dependency-cache] selected Lean toolchain in {relative_to_project(path, project_root)}")

    restored = materialize_cached_lean_artifacts(project_root)
    if restored:
        print(f"[dependency-cache] materialized {len(restored)} cached Lean artifact(s)")

    gaps, warnings = dependency_artifact_report(
        project_root,
        max_missing_mathlib_modules=args.max_missing_mathlib_modules,
    )
    if gaps:
        print(
            "refusing to continue because dependency cache artifacts are missing; "
            "this prevents `lake build` from compiling mathlib.",
            file=sys.stderr,
        )
        for gap in gaps:
            print(f"  {gap}", file=sys.stderr)
        return 1

    for warning in warnings:
        print(f"[dependency-cache] warning: {warning}")
    if cache_status != 0 and not warnings:
        print(
            "[dependency-cache] cache get failed and no missing artifacts were "
            "explicitly tolerated",
            file=sys.stderr,
        )
        return cache_status

    print("[dependency-cache] guarded dependency artifacts present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
