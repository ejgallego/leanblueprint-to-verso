#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ensure_dependency_cache  # noqa: E402


def write_mathlib_manifest(root: Path) -> None:
    manifest = {"packages": [{"name": "mathlib", "rev": "abc", "inputRev": "abc"}]}
    (root / "lake-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def write_mathlib_module(
    package_dir: Path,
    module_name: str,
    artifact_suffixes: tuple[str, ...] = (),
) -> None:
    relative_path = Path(*module_name.split(".")).with_suffix(".lean")
    source_path = package_dir / relative_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("", encoding="utf-8")
    for suffix in artifact_suffixes:
        artifact_path = (
            package_dir / ".lake" / "build" / "lib" / "lean" / relative_path
        ).with_suffix(suffix)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("", encoding="utf-8")


def write_harness_config(
    root: Path,
    formalization_path: str = "Demo",
    wrapper_toolchain_override: str | None = None,
) -> None:
    override_lines = (
        [
            "[harness]",
            f'wrapper_toolchain_override = "{wrapper_toolchain_override}"',
            "",
        ]
        if wrapper_toolchain_override is not None
        else []
    )
    (root / "verso-harness.toml").write_text(
        "\n".join(
            [
                'package_name = "DemoBlueprint"',
                'blueprint_main = "BlueprintMain"',
                f'formalization_path = "{formalization_path}"',
                'chapter_root = "DemoBlueprint/Chapters"',
                'tex_source_glob = "./blueprint/src/chapter/main.tex"',
                "",
                "[lt]",
                "default_chapters = []",
                "",
                *override_lines,
            ]
        )
        + "\n",
        encoding="utf-8",
    )


class EnsureDependencyCacheTests(unittest.TestCase):
    def test_reports_incomplete_mathlib_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(mathlib_dir, "Mathlib.OnlySource")
            gaps = ensure_dependency_cache.dependency_artifact_gaps(root)
        self.assertEqual(
            len(gaps),
            1,
        )
        self.assertIn("cached artifacts incomplete", gaps[0])
        self.assertIn("Mathlib.OnlySource", gaps[0])

    def test_accepts_matching_mathlib_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(
                mathlib_dir,
                "Mathlib.Ready",
                ensure_dependency_cache.REQUIRED_ARTIFACT_SUFFIXES,
            )
            gaps = ensure_dependency_cache.dependency_artifact_gaps(root)
        self.assertEqual(gaps, [])

    def test_tolerates_two_fully_missing_mathlib_modules_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(
                mathlib_dir,
                "Mathlib.Ready",
                ensure_dependency_cache.REQUIRED_ARTIFACT_SUFFIXES,
            )
            write_mathlib_module(mathlib_dir, "Mathlib.MissingOne")
            write_mathlib_module(mathlib_dir, "Mathlib.MissingTwo")

            gaps, warnings = ensure_dependency_cache.dependency_artifact_report(
                root,
                max_missing_mathlib_modules=2,
            )

        self.assertEqual(gaps, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Mathlib.MissingOne", warnings[0])
        self.assertIn("Mathlib.MissingTwo", warnings[0])

    def test_does_not_tolerate_more_missing_mathlib_modules_than_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            for module_name in (
                "Mathlib.Ready",
                "Mathlib.MissingOne",
                "Mathlib.MissingTwo",
                "Mathlib.MissingThree",
            ):
                suffixes = (
                    ensure_dependency_cache.REQUIRED_ARTIFACT_SUFFIXES
                    if module_name == "Mathlib.Ready"
                    else ()
                )
                write_mathlib_module(mathlib_dir, module_name, suffixes)

            gaps = ensure_dependency_cache.dependency_artifact_gaps(
                root,
                max_missing_mathlib_modules=2,
            )

        self.assertEqual(len(gaps), 1)
        self.assertIn("Mathlib.MissingThree", gaps[0])

    def test_does_not_tolerate_partial_mathlib_artifact_sets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(
                mathlib_dir,
                "Mathlib.Partial",
                (".olean", ".trace"),
            )

            gaps = ensure_dependency_cache.dependency_artifact_gaps(
                root,
                max_missing_mathlib_modules=2,
            )

        self.assertEqual(len(gaps), 1)
        self.assertIn("partial artifacts", gaps[0])
        self.assertIn("Mathlib.Partial", gaps[0])

    def test_tolerates_missing_mathlib_umbrella_module_within_explicit_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(mathlib_dir, "Mathlib")

            gaps, warnings = ensure_dependency_cache.dependency_artifact_report(
                root,
                max_missing_mathlib_modules=1,
            )

        self.assertEqual(gaps, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Mathlib", warnings[0])

    def test_noops_when_manifest_has_no_guarded_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lake-manifest.json").write_text(
                json.dumps({"packages": [{"name": "not_mathlib"}]}),
                encoding="utf-8",
            )
            gaps = ensure_dependency_cache.dependency_artifact_gaps(root)
        self.assertEqual(gaps, [])

    def test_sync_project_toolchain_selection_uses_formalization_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(root)
            (root / "lean-toolchain").write_text("leanprover/lean4:v4.30.0\n", encoding="utf-8")
            (root / "Demo").mkdir()
            (root / "Demo" / "lean-toolchain").write_text(
                "leanprover/lean4:v4.30.0-rc2\n",
                encoding="utf-8",
            )
            package_toolchain = (
                root
                / ".lake"
                / "packages"
                / "VersoBlueprint"
                / "lean-toolchain"
            )
            package_toolchain.parent.mkdir(parents=True)
            package_toolchain.write_text("leanprover/lean4:v4.30.0\n", encoding="utf-8")

            changed = ensure_dependency_cache.sync_project_toolchain_selection(root)

            self.assertEqual(
                sorted(path.relative_to(root) for path in changed),
                [Path("lean-toolchain")],
            )
            self.assertEqual(
                (root / "lean-toolchain").read_text(encoding="utf-8").strip(),
                "leanprover/lean4:v4.30.0-rc2",
            )
            self.assertEqual(
                package_toolchain.read_text(encoding="utf-8").strip(),
                "leanprover/lean4:v4.30.0",
            )

    def test_sync_project_toolchain_selection_rejects_wrapper_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(
                root,
                wrapper_toolchain_override="leanprover/lean4:v4.33.0-rc2",
            )
            (root / "lean-toolchain").write_text(
                "leanprover/lean4:v4.33.0-rc2\n",
                encoding="utf-8",
            )
            (root / "Demo").mkdir()
            (root / "Demo" / "lean-toolchain").write_text(
                "leanprover/lean4:v4.33.0-rc1\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(SystemExit, "wrapper_toolchain_override is no longer supported"):
                ensure_dependency_cache.sync_project_toolchain_selection(root)
            self.assertEqual(
                (root / "lean-toolchain").read_text(encoding="utf-8").strip(),
                "leanprover/lean4:v4.33.0-rc2",
            )

    def test_sync_project_toolchain_selection_noops_without_vbp_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(root)
            (root / "Demo").mkdir()
            (root / "Demo" / "lean-toolchain").write_text(
                "leanprover/lean4:v4.30.0-rc2\n",
                encoding="utf-8",
            )

            changed = ensure_dependency_cache.sync_project_toolchain_selection(root)

            self.assertEqual([path.relative_to(root) for path in changed], [Path("lean-toolchain")])
            self.assertFalse(
                (root / ".lake" / "packages" / "VersoBlueprint" / "lean-toolchain").exists()
            )

    def test_warm_cache_does_not_swap_the_selected_root_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_toolchain = root / "lean-toolchain"
            root_toolchain.write_text(
                "leanprover/lean4:v4.33.0-rc1\n",
                encoding="utf-8",
            )
            observed_toolchains: list[str] = []

            def run_cache(
                *args: object,
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                observed_toolchains.append(
                    root_toolchain.read_text(encoding="utf-8").strip()
                )
                return subprocess.CompletedProcess(
                    list(ensure_dependency_cache.CACHE_GET_COMMAND),
                    0,
                )

            with mock.patch.object(
                ensure_dependency_cache.subprocess,
                "run",
                side_effect=run_cache,
            ):
                status = ensure_dependency_cache.warm_cache(root)

            self.assertEqual(status, 0)
            self.assertEqual(
                observed_toolchains,
                ["leanprover/lean4:v4.33.0-rc1"],
            )
            self.assertEqual(
                root_toolchain.read_text(encoding="utf-8"),
                "leanprover/lean4:v4.33.0-rc1\n",
            )

    def test_warm_cache_failure_does_not_mutate_root_toolchain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_toolchain = root / "lean-toolchain"
            root_toolchain.write_text(
                "leanprover/lean4:v4.33.0-rc1\n",
                encoding="utf-8",
            )
            completed = subprocess.CompletedProcess(
                list(ensure_dependency_cache.CACHE_GET_COMMAND),
                1,
            )

            with mock.patch.object(
                ensure_dependency_cache.subprocess,
                "run",
                return_value=completed,
            ):
                status = ensure_dependency_cache.warm_cache(root)

            self.assertEqual(status, 1)
            self.assertEqual(
                root_toolchain.read_text(encoding="utf-8"),
                "leanprover/lean4:v4.33.0-rc1\n",
            )

    def test_main_continues_after_cache_misses_within_explicit_tolerance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(root)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(
                mathlib_dir,
                "Mathlib.Ready",
                ensure_dependency_cache.REQUIRED_ARTIFACT_SUFFIXES,
            )
            write_mathlib_module(mathlib_dir, "Mathlib.MissingOne")
            write_mathlib_module(mathlib_dir, "Mathlib.MissingTwo")
            argv = [
                "ensure_dependency_cache.py",
                "--project-root",
                str(root),
                "--warm-cache",
                "--max-missing-mathlib-modules",
                "2",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    ensure_dependency_cache,
                    "sync_project_toolchain_selection",
                    return_value=[],
                ),
                mock.patch.object(ensure_dependency_cache, "warm_cache", return_value=1),
                mock.patch.object(
                    ensure_dependency_cache,
                    "materialize_cached_lean_artifacts",
                    return_value=[],
                ),
            ):
                status = ensure_dependency_cache.main()

        self.assertEqual(status, 0)

    def test_main_keeps_two_missing_modules_strict_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(root)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(mathlib_dir, "Mathlib.MissingOne")
            write_mathlib_module(mathlib_dir, "Mathlib.MissingTwo")
            argv = [
                "ensure_dependency_cache.py",
                "--project-root",
                str(root),
                "--warm-cache",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    ensure_dependency_cache,
                    "sync_project_toolchain_selection",
                    return_value=[],
                ),
                mock.patch.object(ensure_dependency_cache, "warm_cache", return_value=1),
                mock.patch.object(
                    ensure_dependency_cache,
                    "materialize_cached_lean_artifacts",
                    return_value=[],
                ),
            ):
                status = ensure_dependency_cache.main()

        self.assertEqual(status, 1)

    def test_main_still_fails_cache_get_error_without_tolerated_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_harness_config(root)
            write_mathlib_manifest(root)
            mathlib_dir = root / ".lake" / "packages" / "mathlib"
            write_mathlib_module(
                mathlib_dir,
                "Mathlib.Ready",
                ensure_dependency_cache.REQUIRED_ARTIFACT_SUFFIXES,
            )
            argv = [
                "ensure_dependency_cache.py",
                "--project-root",
                str(root),
                "--warm-cache",
                "--max-missing-mathlib-modules",
                "2",
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    ensure_dependency_cache,
                    "sync_project_toolchain_selection",
                    return_value=[],
                ),
                mock.patch.object(ensure_dependency_cache, "warm_cache", return_value=1),
                mock.patch.object(
                    ensure_dependency_cache,
                    "materialize_cached_lean_artifacts",
                    return_value=[],
                ),
            ):
                status = ensure_dependency_cache.main()

        self.assertEqual(status, 1)

    def test_materializes_cached_lean_artifacts_from_dependency_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            cache = Path(tmp) / "cache"
            trace = (
                root
                / ".lake"
                / "packages"
                / "verso"
                / ".lake"
                / "build"
                / "lib"
                / "lean"
                / "VersoManual"
                / "Basic.trace"
            )
            trace.parent.mkdir(parents=True)
            cache.mkdir()
            trace.write_text(
                json.dumps(
                    {
                        "outputs": {
                            "o": [
                                "abc.olean",
                                "def.olean.server",
                                "ghi.olean.private",
                            ],
                            "i": "jkl.ilean",
                            "c": "ignored.c",
                            "m": False,
                        }
                    }
                ),
                encoding="utf-8",
            )
            for artifact_name in [
                "abc.olean",
                "def.olean.server",
                "ghi.olean.private",
                "jkl.ilean",
            ]:
                (cache / artifact_name).write_text(artifact_name, encoding="utf-8")

            restored = ensure_dependency_cache.materialize_cached_lean_artifacts(root, cache)

            self.assertEqual(
                sorted(path.name for path in restored),
                [
                    "Basic.ilean",
                    "Basic.olean",
                    "Basic.olean.private",
                    "Basic.olean.server",
                ],
            )
            self.assertEqual(
                (trace.parent / "Basic.olean").read_text(encoding="utf-8"),
                "abc.olean",
            )
            self.assertEqual(
                (trace.parent / "Basic.olean.server").read_text(encoding="utf-8"),
                "def.olean.server",
            )
            self.assertEqual(
                (trace.parent / "Basic.olean.private").read_text(encoding="utf-8"),
                "ghi.olean.private",
            )
            self.assertEqual(
                (trace.parent / "Basic.ilean").read_text(encoding="utf-8"),
                "jkl.ilean",
            )
            self.assertFalse((trace.parent / "Basic.c").exists())

    def test_lake_cache_artifacts_dir_falls_back_to_elan_resolved_lake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shim_lake = root / ".elan" / "bin" / "lake"
            real_lake = root / ".elan" / "toolchains" / "leanprover--lean4---v4.30.0-rc2" / "bin" / "lake"
            artifact_dir = real_lake.parents[1] / "lake" / "cache" / "artifacts"
            shim_lake.parent.mkdir(parents=True)
            real_lake.parent.mkdir(parents=True)
            artifact_dir.mkdir(parents=True)
            shim_lake.write_text("", encoding="utf-8")
            real_lake.write_text("", encoding="utf-8")

            completed = subprocess.CompletedProcess(
                ["elan", "which", "lake"],
                0,
                stdout=str(real_lake) + "\n",
                stderr="",
            )
            with mock.patch.object(ensure_dependency_cache.shutil, "which", return_value=str(shim_lake)):
                with mock.patch.object(ensure_dependency_cache.subprocess, "run", return_value=completed):
                    self.assertEqual(
                        ensure_dependency_cache.lake_cache_artifacts_dir(),
                        artifact_dir,
                    )


if __name__ == "__main__":
    unittest.main()
