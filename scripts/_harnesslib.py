#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


CONFIG_FILENAME = "verso-harness.toml"
PACKAGE_PATTERN = re.compile(r"^\s*package\s+([A-Za-z_][A-Za-z0-9_]*)\s+where", re.M)
GITHUB_REPO_PATTERN = re.compile(
    r"^(?:git@github\.com:|https://github\.com/)(?P<slug>[^/]+/[^/.]+?)(?:\.git)?/?$"
)
VERSO_BLUEPRINT_REQUIRE_PATTERN = re.compile(
    r'^\s*require\s+VersoBlueprint\s+from\s+git\s+"(?P<url>[^"]+)"\s*@\s*"(?P<ref>[^"]+)"',
    re.M,
)
LAKE_BOOL_OPTION_PATTERN = re.compile(
    r'⟨`(?P<name>[A-Za-z0-9_.]+),\s*(?P<value>true|false)\s*⟩'
)
LAKE_NAT_OPTION_PATTERN = re.compile(
    r'⟨`(?P<name>[A-Za-z0-9_.]+),\s*\.ofNat\s+(?P<value>\d+)\s*⟩'
)
DEFAULT_LT_NODE_KIND_PAIRS = (
    ("theorem", "theorem"),
    ("definition", "definition"),
    ("lemma", "lemma_"),
    ("corollary", "corollary"),
    ("proof", "proof"),
)
DEFAULT_NATIVE_WARNINGS = False
DEFAULT_DOCSTRING_WARNINGS = False
DEFAULT_STRICT_EXTERNAL_CODE = True
@dataclass(frozen=True)
class HarnessConfig:
    package_name: str
    blueprint_main: str
    formalization_path: str
    chapter_root: str
    tex_source_glob: str
    lt_default_chapters: tuple[str, ...]
    lt_node_kind_pairs: tuple[tuple[str, str], ...]
    lt_source_files: tuple[tuple[str, tuple[str, ...]], ...]
    lt_lean_target_aliases: tuple[tuple[str, str], ...]
    lt_unresolved_lean_targets: tuple[str, ...]
    native_warnings: bool
    docstring_warnings: bool
    strict_external_code: bool


def resolve_project_root(raw: Path | None) -> Path:
    return (raw or Path.cwd()).resolve()


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_FILENAME


def find_package_name(project_root: Path) -> str | None:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None
    match = PACKAGE_PATTERN.search(lakefile.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def parse_github_repo_slug(url: str) -> str | None:
    match = GITHUB_REPO_PATTERN.fullmatch(url.strip())
    if match is None:
        return None
    return match.group("slug")


def extract_lean_release(lean_toolchain: str) -> str:
    value = lean_toolchain.strip()
    return value.rsplit(":", 1)[-1] if ":" in value else value


def default_verso_blueprint_ref(lean_toolchain: str) -> str:
    release = extract_lean_release(lean_toolchain)
    release_match = re.fullmatch(r"v?(?P<base>\d+\.\d+\.\d+)(?:[-+].*)?", release)
    if release_match is not None:
        return f"v{release_match.group('base')}"
    if release.startswith("v"):
        return release
    return release


def normalize_verso_blueprint_ref(ref: str) -> str:
    value = ref.strip()
    if value.startswith("lean-"):
        value = value[len("lean-") :]
    if re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.]+)?", value):
        return f"v{value}"
    return value


def verso_blueprint_uses_weak_options(ref: str | None) -> bool:
    return True


def verso_blueprint_option_name(ref: str | None, suffix: str) -> str:
    prefix = "weak.verso" if verso_blueprint_uses_weak_options(ref) else "verso"
    return f"{prefix}.{suffix}"


def verso_math_lint_option_name(ref: str | None) -> str:
    return verso_blueprint_option_name(ref, "blueprint.math.lint")


def verso_strict_external_code_option_name(ref: str | None) -> str:
    return verso_blueprint_option_name(ref, "blueprint.externalCode.strictResolve")


def verso_warn_line_length_option_name(ref: str | None) -> str:
    return verso_blueprint_option_name(ref, "code.warnLineLength")


def read_verso_blueprint_requirement(project_root: Path) -> tuple[str | None, str | None]:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None, None

    match = VERSO_BLUEPRINT_REQUIRE_PATTERN.search(lakefile.read_text(encoding="utf-8"))
    if match is None:
        return None, None

    return match.group("url"), match.group("ref")


def find_verso_blueprint_dependency(project_root: Path) -> tuple[str | None, str | None]:
    url, ref = read_verso_blueprint_requirement(project_root)
    if url is None or ref is None:
        return None, None

    repo = parse_github_repo_slug(url)
    return repo, ref


def find_lake_lean_option_bool(project_root: Path, option_name: str) -> bool | None:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None

    for match in LAKE_BOOL_OPTION_PATTERN.finditer(lakefile.read_text(encoding="utf-8")):
        if match.group("name") == option_name:
            return match.group("value") == "true"
    return None


def find_lake_lean_option_nat(project_root: Path, option_name: str) -> int | None:
    lakefile = project_root / "lakefile.lean"
    if not lakefile.exists():
        return None

    for match in LAKE_NAT_OPTION_PATTERN.finditer(lakefile.read_text(encoding="utf-8")):
        if match.group("name") == option_name:
            return int(match.group("value"))
    return None


def require_relative_path(value: str, field_name: str) -> str:
    if Path(value).is_absolute():
        raise SystemExit(f"{CONFIG_FILENAME}: {field_name} must be a relative path, got: {value!r}")
    return value


def require_string(table: dict[str, object], key: str, field_name: str) -> str:
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
    return value


def require_bool(table: dict[str, object], key: str, field_name: str) -> bool:
    value = table.get(key)
    if not isinstance(value, bool):
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
    return value


def require_string_list(
    table: dict[str, object],
    key: str,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
    items = tuple(item for item in value)
    if not allow_empty and not items:
        raise SystemExit(f"{CONFIG_FILENAME}: {field_name} must not be empty")
    return items


def require_string_table(
    table: dict[str, object],
    key: str,
    field_name: str,
    *,
    allow_empty: bool,
) -> tuple[tuple[str, str], ...]:
    value = table.get(key)
    if not isinstance(value, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")

    items: list[tuple[str, str]] = []
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid {field_name}")
        items.append((raw_key.strip(), raw_value.strip()))

    if not allow_empty and not items:
        raise SystemExit(f"{CONFIG_FILENAME}: {field_name} must not be empty")
    return tuple(items)


def load_lt_node_kind_pairs(lt_section: dict[str, object]) -> tuple[tuple[str, str], ...]:
    if "node_kinds" not in lt_section:
        return DEFAULT_LT_NODE_KIND_PAIRS

    overrides = require_string_table(
        lt_section,
        "node_kinds",
        "lt.node_kinds",
        allow_empty=False,
    )
    merged = dict(DEFAULT_LT_NODE_KIND_PAIRS)
    merged.update(overrides)

    ordered_pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for tex_kind, verso_kind in DEFAULT_LT_NODE_KIND_PAIRS:
        ordered_pairs.append((tex_kind, merged[tex_kind]))
        seen.add(tex_kind)
    for tex_kind, _ in overrides:
        if tex_kind in seen:
            continue
        ordered_pairs.append((tex_kind, merged[tex_kind]))
        seen.add(tex_kind)
    return tuple(ordered_pairs)


def load_lt_source_files(
    lt_section: dict[str, object],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    value = lt_section.get("source_files")
    if value is None:
        return ()
    if not isinstance(value, dict) or not value:
        raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid lt.source_files")

    mappings: list[tuple[str, tuple[str, ...]]] = []
    for raw_chapter, raw_sources in value.items():
        if not isinstance(raw_chapter, str) or not raw_chapter.strip():
            raise SystemExit(f"{CONFIG_FILENAME}: missing or invalid lt.source_files")
        if (
            not isinstance(raw_sources, list)
            or not raw_sources
            or any(not isinstance(source, str) or not source.strip() for source in raw_sources)
        ):
            raise SystemExit(
                f"{CONFIG_FILENAME}: lt.source_files.{raw_chapter} must be a non-empty string list"
            )
        chapter = require_relative_path(raw_chapter.strip(), "lt.source_files chapter")
        sources = tuple(
            require_relative_path(source.strip(), f"lt.source_files.{raw_chapter}")
            for source in raw_sources
        )
        mappings.append((chapter, sources))
    return tuple(mappings)


def load_lt_lean_target_policy(
    lt_section: dict[str, object],
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    aliases = (
        require_string_table(
            lt_section,
            "lean_target_aliases",
            "lt.lean_target_aliases",
            allow_empty=False,
        )
        if "lean_target_aliases" in lt_section
        else ()
    )
    unresolved = (
        tuple(
            target.strip()
            for target in require_string_list(
                lt_section,
                "unresolved_lean_targets",
                "lt.unresolved_lean_targets",
                allow_empty=False,
            )
        )
        if "unresolved_lean_targets" in lt_section
        else ()
    )

    alias_sources = {source for source, _ in aliases}
    duplicate_unresolved = sorted(
        target for target in set(unresolved) if unresolved.count(target) > 1
    )
    if duplicate_unresolved:
        raise SystemExit(
            f"{CONFIG_FILENAME}: lt.unresolved_lean_targets contains duplicates: "
            f"{duplicate_unresolved}"
        )
    overlap = sorted(alias_sources & set(unresolved))
    if overlap:
        raise SystemExit(
            f"{CONFIG_FILENAME}: Lean targets cannot be both aliased and unresolved: {overlap}"
        )
    self_aliases = sorted(source for source, target in aliases if source == target)
    if self_aliases:
        raise SystemExit(
            f"{CONFIG_FILENAME}: lt.lean_target_aliases contains no-op aliases: {self_aliases}"
        )
    return aliases, unresolved


def load_config(project_root: Path) -> HarnessConfig:
    path = config_path(project_root)
    if not path.exists():
        raise SystemExit(
            f"missing required {CONFIG_FILENAME} at {path}; helper-managed repos must declare "
            "their harness layout explicitly"
        )

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{CONFIG_FILENAME}: invalid TOML: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: expected a top-level table")

    package_name = require_string(data, "package_name", "package_name")
    blueprint_main = require_string(data, "blueprint_main", "blueprint_main")
    formalization_path = require_relative_path(
        require_string(data, "formalization_path", "formalization_path"),
        "formalization_path",
    )
    chapter_root = require_relative_path(
        require_string(data, "chapter_root", "chapter_root"),
        "chapter_root",
    )
    tex_source_glob = require_relative_path(
        require_string(data, "tex_source_glob", "tex_source_glob"),
        "tex_source_glob",
    )

    lt_section = data.get("lt")
    if not isinstance(lt_section, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: missing required [lt] table")
    lt_default_chapters = require_string_list(
        lt_section,
        "default_chapters",
        "lt.default_chapters",
        allow_empty=True,
    )
    lt_node_kind_pairs = load_lt_node_kind_pairs(lt_section)
    lt_source_files = load_lt_source_files(lt_section)
    lt_lean_target_aliases, lt_unresolved_lean_targets = load_lt_lean_target_policy(
        lt_section
    )
    for chapter in lt_default_chapters:
        require_relative_path(chapter, "lt.default_chapters")

    if lt_source_files:
        source_chapters = {chapter for chapter, _ in lt_source_files}
        default_chapters = set(lt_default_chapters)
        missing = sorted(default_chapters - source_chapters)
        extra = sorted(source_chapters - default_chapters)
        if missing:
            raise SystemExit(
                f"{CONFIG_FILENAME}: lt.source_files is missing default chapters: {missing}"
            )
        if extra:
            raise SystemExit(
                f"{CONFIG_FILENAME}: lt.source_files contains non-default chapters: {extra}"
            )

    harness_section = data.get("harness", {})
    if not isinstance(harness_section, dict):
        raise SystemExit(f"{CONFIG_FILENAME}: invalid [harness] table")
    native_warnings = (
        require_bool(harness_section, "native_warnings", "harness.native_warnings")
        if "native_warnings" in harness_section
        else DEFAULT_NATIVE_WARNINGS
    )
    docstring_warnings = (
        require_bool(harness_section, "docstring_warnings", "harness.docstring_warnings")
        if "docstring_warnings" in harness_section
        else DEFAULT_DOCSTRING_WARNINGS
    )
    strict_external_code = (
        require_bool(harness_section, "strict_external_code", "harness.strict_external_code")
        if "strict_external_code" in harness_section
        else DEFAULT_STRICT_EXTERNAL_CODE
    )
    if "wrapper_toolchain_override" in harness_section:
        raise SystemExit(
            f"{CONFIG_FILENAME}: harness.wrapper_toolchain_override is no longer supported; "
            "the wrapper and vendored formalization must use the same Lean toolchain. "
            "Select newer Blueprint tooling through the VersoBlueprint dependency and reusable workflow ref."
        )
    if "verso_blueprint_ref" in harness_section:
        raise SystemExit(
            f"{CONFIG_FILENAME}: harness.verso_blueprint_ref is no longer supported; "
            "keep prerelease Lean toolchain adaptations local and pin VersoBlueprint "
            "to the base release ref"
        )
    if "non_port_chapters" in harness_section:
        raise SystemExit(
            f"{CONFIG_FILENAME}: harness.non_port_chapters is no longer supported; "
            "every chapter under chapter_root must correspond to upstream TeX source "
            "and be listed in lt.default_chapters"
        )

    chapter_root_path = Path(chapter_root)
    for chapter in lt_default_chapters:
        chapter_path = Path(chapter)
        if chapter_root_path != Path(".") and chapter_root_path not in chapter_path.parents:
            raise SystemExit(
                f"{CONFIG_FILENAME}: chapter {chapter!r} is not under chapter_root {chapter_root!r}"
            )

    return HarnessConfig(
        package_name=package_name,
        blueprint_main=blueprint_main,
        formalization_path=formalization_path,
        chapter_root=chapter_root,
        tex_source_glob=tex_source_glob,
        lt_default_chapters=lt_default_chapters,
        lt_node_kind_pairs=lt_node_kind_pairs,
        lt_source_files=lt_source_files,
        lt_lean_target_aliases=lt_lean_target_aliases,
        lt_unresolved_lean_targets=lt_unresolved_lean_targets,
        native_warnings=native_warnings,
        docstring_warnings=docstring_warnings,
        strict_external_code=strict_external_code,
    )


def resolve_input_paths(project_root: Path, raw_paths: list[Path]) -> list[Path]:
    paths: list[Path] = []
    for raw_path in raw_paths:
        if raw_path.is_absolute():
            paths.append(raw_path.resolve())
        else:
            paths.append((project_root / raw_path).resolve())
    return paths


def default_chapter_paths(project_root: Path) -> list[Path]:
    config = load_config(project_root)
    return resolve_input_paths(project_root, [Path(path) for path in config.lt_default_chapters])


def resolve_chapter_paths(project_root: Path, raw_paths: list[Path]) -> list[Path]:
    load_config(project_root)
    return resolve_input_paths(project_root, raw_paths) if raw_paths else default_chapter_paths(project_root)


def lean_file_to_module(project_root: Path, path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(project_root)
    except ValueError:
        return None

    if relative.suffix != ".lean":
        return None

    return ".".join(relative.with_suffix("").parts)
