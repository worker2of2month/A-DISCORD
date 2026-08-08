"""Load generated-output ownership data and run its safe command pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REGISTRY_PATH = Path("tools/data/generated_output_owners.json")
REQUIRED_FIELDS = {
    "id",
    "owner_module",
    "output_globs",
    "source_inputs",
    "check_command",
    "apply_command",
    "may_delete_outputs",
    "ownership_mode",
}
OWNERSHIP_MODES = {"exclusive", "layered"}


def _nonempty_strings(value: object, field: str, family_id: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{family_id}: {field} must be a non-empty list of strings")
    return value


def _validate_relative_patterns(patterns: Sequence[str], field: str, family_id: str) -> None:
    for pattern in patterns:
        candidate = Path(pattern)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"{family_id}: {field} patterns must be repository-relative")


def _expanded_paths(root: Path, patterns: Sequence[str]) -> set[Path]:
    paths: set[Path] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError(f"generated-output path escapes repository root: {pattern}")
            if resolved.exists():
                paths.add(resolved)
    return paths


def _expanded_outputs(root: Path, entry: Mapping[str, Any]) -> set[Path]:
    return {
        path
        for path in _expanded_paths(root, entry["output_globs"])
        if path.is_file()
    }


def _validate_overlaps(root: Path, families: Sequence[Mapping[str, Any]]) -> None:
    owners_by_path: dict[Path, list[Mapping[str, Any]]] = {}
    for entry in families:
        for path in _expanded_outputs(root, entry):
            owners_by_path.setdefault(path, []).append(entry)
    for path, owners in owners_by_path.items():
        if len(owners) < 2:
            continue
        exclusive = [entry["id"] for entry in owners if entry["ownership_mode"] == "exclusive"]
        if exclusive:
            relative = path.relative_to(root.resolve())
            ids = ", ".join(entry["id"] for entry in owners)
            raise ValueError(f"exclusive generated-output overlap at {relative}: {ids}")


def load_registry(root: Path | str) -> dict[str, Any]:
    """Load and strictly validate the generated-output registry for *root*."""

    root_path = Path(root).resolve()
    payload = json.loads((root_path / REGISTRY_PATH).read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError("generated-output registry schema must be 1")
    families = payload.get("families")
    if not isinstance(families, list) or not families:
        raise ValueError("generated-output registry must contain families")

    ids: set[str] = set()
    for entry in families:
        if not isinstance(entry, dict):
            raise ValueError("each generated-output family must be an object")
        missing = REQUIRED_FIELDS - set(entry)
        if missing:
            raise ValueError(f"generated-output family is missing fields: {sorted(missing)}")
        family_id = entry["id"]
        if not isinstance(family_id, str) or not family_id.strip():
            raise ValueError("generated-output family id must be a non-empty string")
        if family_id in ids:
            raise ValueError(f"duplicate generated-output family id: {family_id}")
        ids.add(family_id)
        if not isinstance(entry["owner_module"], str) or not entry["owner_module"].startswith(
            "tools.builders.build_"
        ):
            raise ValueError(f"{family_id}: owner_module must name a packaged builder")
        output_globs = _nonempty_strings(entry["output_globs"], "output_globs", family_id)
        source_inputs = _nonempty_strings(entry["source_inputs"], "source_inputs", family_id)
        _validate_relative_patterns(output_globs, "output_globs", family_id)
        _validate_relative_patterns(source_inputs, "source_inputs", family_id)
        check = _nonempty_strings(entry["check_command"], "check_command", family_id)
        apply = _nonempty_strings(entry["apply_command"], "apply_command", family_id)
        if check != ["{python}", "-B", "-m", entry["owner_module"]]:
            raise ValueError(f"{family_id}: check_command must invoke the builder default")
        if apply != [*check, "--apply"]:
            raise ValueError(f"{family_id}: apply_command must append --apply to check_command")
        if not isinstance(entry["may_delete_outputs"], bool):
            raise ValueError(f"{family_id}: may_delete_outputs must be boolean")
        if entry["ownership_mode"] not in OWNERSHIP_MODES:
            raise ValueError(f"{family_id}: invalid ownership_mode")
        if entry["ownership_mode"] == "layered" and not str(
            entry.get("overlap_explanation", "")
        ).strip():
            raise ValueError(f"{family_id}: layered ownership needs overlap_explanation")
        if not _expanded_outputs(root_path, entry):
            raise ValueError(f"{family_id}: output_globs must materialize at least one current file")
        for source_pattern in source_inputs:
            if not _expanded_paths(root_path, [source_pattern]):
                raise ValueError(
                    f"{family_id}: source_inputs pattern {source_pattern} must materialize "
                    "at least one current path"
                )

    sequence = payload.get("apply_sequence")
    if not isinstance(sequence, list) or not sequence or not all(
        isinstance(family_id, str) and family_id for family_id in sequence
    ):
        raise ValueError("apply_sequence must be a non-empty list of family ids")
    unknown = set(sequence) - ids
    missing = ids - set(sequence)
    if unknown or missing:
        raise ValueError(
            f"apply_sequence coverage differs: unknown={sorted(unknown)}, missing={sorted(missing)}"
        )
    expected_counts = Counter({family_id: 1 for family_id in ids})
    if "northern_countries" in expected_counts:
        expected_counts["northern_countries"] = 2
    if Counter(sequence) != expected_counts:
        raise ValueError("apply_sequence must list each family once and northern_countries twice")
    _validate_overlaps(root_path, families)
    return payload


def _resolved_command(command: Iterable[str]) -> list[str]:
    return [sys.executable if part == "{python}" else part for part in command]


def run_registered_command(
    root: Path | str,
    command: Iterable[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run one registry command from *root* with bytecode writes disabled."""

    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        _resolved_command(command),
        cwd=Path(root).resolve(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=environment,
    )


def snapshot_outputs(root: Path | str, registry: Mapping[str, Any]) -> dict[str, str]:
    """Hash the full union of files currently claimed by registry owners."""

    root_path = Path(root).resolve()
    paths: set[Path] = set()
    for entry in registry["families"]:
        paths.update(_expanded_outputs(root_path, entry))
    return {
        path.relative_to(root_path).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths, key=lambda item: item.relative_to(root_path).as_posix())
    }


def validated_sandbox_root(
    candidate: Path | str,
    *,
    authoritative_root: Path | str,
) -> Path:
    """Return a disposable full-repository root, rejecting the live checkout."""

    sandbox = Path(candidate).resolve(strict=True)
    authoritative = Path(authoritative_root).resolve(strict=True)
    if not sandbox.is_dir():
        raise ValueError(f"generator sandbox is not a directory: {sandbox}")
    if (
        sandbox.samefile(authoritative)
        or sandbox.is_relative_to(authoritative)
        or authoritative.is_relative_to(sandbox)
    ):
        raise ValueError("generator sandbox overlaps the authoritative repository")
    for marker in ("descriptor.mod", REGISTRY_PATH):
        if not (sandbox / marker).exists():
            raise ValueError(f"generator sandbox is not a full A-Discord tree: missing {marker}")
    return sandbox


def run_apply_pipeline(
    root: Path | str,
    registry: Mapping[str, Any],
    *,
    timeout: int,
) -> None:
    """Run one complete explicit apply sequence, including layered repeats."""

    entries = {entry["id"]: entry for entry in registry["families"]}
    for family_id in registry["apply_sequence"]:
        result = run_registered_command(root, entries[family_id]["apply_command"], timeout=timeout)
        if result.returncode:
            raise RuntimeError(
                f"generated-output apply failed for {family_id} ({result.returncode})\n"
                f"{result.stdout}{result.stderr}"
            )
