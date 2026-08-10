#!/usr/bin/env python3
"""Assign A-Discord lore trade regions to the continent column of definition.csv.

The source manifest describes geography through strategic regions plus explicit
state-level boundaries.  Starting owners are deliberately ignored: conquest or
country-generator changes must not move a province between trade filters.
"""

from __future__ import annotations

import argparse
import codecs
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from tools.lib.paths import repository_root


ROOT = repository_root()
MANIFEST_RELATIVE = Path("tools/data/adiscord_trade_region_map.json")
CONTINENT_RELATIVE = Path("map/continent.txt")
DEFINITION_RELATIVE = Path("map/definition.csv")
STATE_DIRECTORY = Path("history/states")
STRATEGIC_REGION_DIRECTORY = Path("map/strategicregions")
EXPECTED_CONTINENT_KEYS = (
    "europe",
    "north_america",
    "south_america",
    "australia",
    "africa",
    "asia",
    "middle_east",
)


@dataclass(frozen=True)
class TradeRegionPlan:
    content: bytes
    continent_keys: tuple[str, ...]
    state_continents: Mapping[int, int]
    state_regions: Mapping[int, int]
    province_continents: Mapping[int, int]
    state_counts: Mapping[int, int]
    province_counts: Mapping[int, int]


def _without_comments(source: str) -> str:
    return re.sub(r"(?m)#.*$", "", source)


def _read_block(source: str, key: str, path: Path) -> str:
    match = re.search(rf"\b{re.escape(key)}\s*=\s*\{{([^}}]*)\}}", source, re.DOTALL)
    if not match:
        raise RuntimeError(f"{path}: missing {key} block")
    return match.group(1)


def load_continent_keys(root: Path = ROOT) -> tuple[str, ...]:
    path = root / CONTINENT_RELATIVE
    source = _without_comments(path.read_text(encoding="utf-8-sig", errors="strict"))
    block = _read_block(source, "continents", path)
    keys = tuple(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", block))
    if keys != EXPECTED_CONTINENT_KEYS:
        raise RuntimeError(
            f"{path}: expected continent order {EXPECTED_CONTINENT_KEYS}, found {keys}"
        )
    return keys


def _parse_definition(source: bytes, path: Path) -> dict[int, str]:
    payload = source[len(codecs.BOM_UTF8) :] if source.startswith(codecs.BOM_UTF8) else source
    definitions: dict[int, str] = {}
    for line_number, raw_line in enumerate(payload.splitlines(keepends=True), 1):
        body, _ = _split_line_ending(raw_line)
        if not body:
            raise RuntimeError(f"{path}:{line_number}: blank definition row")
        fields = body.split(b";")
        if len(fields) != 8:
            raise RuntimeError(
                f"{path}:{line_number}: expected 8 semicolon fields, found {len(fields)}"
            )
        try:
            province = int(fields[0])
            province_type = fields[4].decode("ascii").strip().lower()
        except (UnicodeDecodeError, ValueError) as exc:
            raise RuntimeError(f"{path}:{line_number}: invalid definition row") from exc
        if province in definitions:
            raise RuntimeError(f"{path}:{line_number}: duplicate province {province}")
        definitions[province] = province_type
    if 0 not in definitions or definitions[0] != "land":
        raise RuntimeError(f"{path}: province 0 must remain the land sentinel")
    return definitions


def _split_line_ending(raw_line: bytes) -> tuple[bytes, bytes]:
    for ending in (b"\r\n", b"\n", b"\r"):
        if raw_line.endswith(ending):
            return raw_line[: -len(ending)], ending
    return raw_line, b""


def rewrite_continent_column(
    source: bytes,
    continent_by_province: Mapping[int, int],
    *,
    path: Path = DEFINITION_RELATIVE,
) -> bytes:
    """Return *source* with only field 7 changed, preserving all byte layout."""

    definitions = _parse_definition(source, path)
    real_land = {
        province
        for province, province_type in definitions.items()
        if province != 0 and province_type == "land"
    }
    supplied = set(continent_by_province)
    if supplied != real_land:
        raise RuntimeError(
            f"{path}: continent coverage differs from real land provinces; "
            f"missing={sorted(real_land - supplied)[:12]}, "
            f"unexpected={sorted(supplied - real_land)[:12]}"
        )

    has_bom = source.startswith(codecs.BOM_UTF8)
    payload = source[len(codecs.BOM_UTF8) :] if has_bom else source
    rendered: list[bytes] = []
    for raw_line in payload.splitlines(keepends=True):
        body, ending = _split_line_ending(raw_line)
        fields = body.split(b";")
        province = int(fields[0])
        province_type = fields[4].decode("ascii").strip().lower()
        if province == 0 or province_type != "land":
            expected = 0
        else:
            expected = continent_by_province[province]
            if expected not in range(1, 8):
                raise RuntimeError(f"{path}: province {province} has invalid continent {expected}")
        fields[7] = str(expected).encode("ascii")
        rendered.append(b";".join(fields) + ending)
    return (codecs.BOM_UTF8 if has_bom else b"") + b"".join(rendered)


def _parse_state_files(root: Path) -> tuple[dict[int, set[int]], dict[int, Path]]:
    states: dict[int, set[int]] = {}
    paths: dict[int, Path] = {}
    for path in sorted((root / STATE_DIRECTORY).glob("*.txt")):
        source = _without_comments(path.read_text(encoding="utf-8-sig", errors="strict"))
        id_match = re.search(r"\bid\s*=\s*(\d+)", source)
        if not id_match:
            raise RuntimeError(f"{path}: missing state id")
        state_id = int(id_match.group(1))
        if state_id in states:
            raise RuntimeError(f"{path}: duplicate state id {state_id} also in {paths[state_id]}")
        provinces = [int(value) for value in re.findall(r"\d+", _read_block(source, "provinces", path))]
        if not provinces or len(provinces) != len(set(provinces)):
            raise RuntimeError(f"{path}: empty or duplicate province list")
        states[state_id] = set(provinces)
        paths[state_id] = path
    if not states:
        raise RuntimeError(f"{root / STATE_DIRECTORY}: no state files found")
    return states, paths


def _parse_strategic_regions(root: Path) -> tuple[dict[int, set[int]], dict[int, int]]:
    regions: dict[int, set[int]] = {}
    region_by_province: dict[int, int] = {}
    for path in sorted((root / STRATEGIC_REGION_DIRECTORY).glob("*.txt")):
        source = _without_comments(path.read_text(encoding="utf-8-sig", errors="strict"))
        id_match = re.search(r"\bid\s*=\s*(\d+)", source)
        if not id_match:
            raise RuntimeError(f"{path}: missing strategic-region id")
        region_id = int(id_match.group(1))
        if region_id in regions:
            raise RuntimeError(f"{path}: duplicate strategic-region id {region_id}")
        provinces = {
            int(value) for value in re.findall(r"\d+", _read_block(source, "provinces", path))
        }
        if not provinces:
            raise RuntimeError(f"{path}: empty province list")
        for province in provinces:
            previous = region_by_province.get(province)
            if previous is not None:
                raise RuntimeError(
                    f"{path}: province {province} appears in strategic regions "
                    f"{previous} and {region_id}"
                )
            region_by_province[province] = region_id
        regions[region_id] = provinces
    if not regions:
        raise RuntimeError(f"{root / STRATEGIC_REGION_DIRECTORY}: no region files found")
    return regions, region_by_province


def _load_manifest(root: Path) -> dict[str, object]:
    path = root / MANIFEST_RELATIVE
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1:
        raise RuntimeError(f"{path}: schema must be 1")
    if manifest.get("default_continent") != 7:
        raise RuntimeError(f"{path}: Outer Lands continent 7 must be the default")
    continents = manifest.get("continents")
    if not isinstance(continents, list) or len(continents) != 7:
        raise RuntimeError(f"{path}: expected seven continent entries")
    return manifest


def build_plan(root: Path = ROOT) -> TradeRegionPlan:
    root = root.resolve()
    continent_keys = load_continent_keys(root)
    manifest = _load_manifest(root)
    definition_path = root / DEFINITION_RELATIVE
    definition_source = definition_path.read_bytes()
    definitions = _parse_definition(definition_source, definition_path)
    real_land = {
        province
        for province, province_type in definitions.items()
        if province != 0 and province_type == "land"
    }

    states, state_paths = _parse_state_files(root)
    state_by_province: dict[int, int] = {}
    for state_id, provinces in states.items():
        for province in provinces:
            if province not in definitions:
                raise RuntimeError(f"{state_paths[state_id]}: unknown province {province}")
            if definitions[province] == "lake":
                # HOI4 permits a lake province to be listed in its surrounding
                # state.  Lakes still keep continent 0 and do not define the
                # state's trade geography.
                continue
            if definitions[province] != "land":
                raise RuntimeError(f"{state_paths[state_id]}: non-land province {province}")
            previous = state_by_province.get(province)
            if previous is not None:
                raise RuntimeError(
                    f"province {province} is assigned to states {previous} and {state_id}"
                )
            state_by_province[province] = state_id
    if set(state_by_province) != real_land:
        raise RuntimeError(
            "state coverage differs from real land provinces; "
            f"missing={sorted(real_land - set(state_by_province))[:12]}, "
            f"unexpected={sorted(set(state_by_province) - real_land)[:12]}"
        )

    regions, region_by_province = _parse_strategic_regions(root)
    missing_regions = real_land - set(region_by_province)
    if missing_regions:
        raise RuntimeError(
            f"strategic regions do not cover land provinces {sorted(missing_regions)[:12]}"
        )
    state_regions: dict[int, int] = {}
    for state_id, provinces in states.items():
        state_land = {
            province for province in provinces if definitions[province] == "land"
        }
        if not state_land:
            raise RuntimeError(f"{state_paths[state_id]}: state has no land provinces")
        state_region_ids = {region_by_province[province] for province in state_land}
        if len(state_region_ids) != 1:
            raise RuntimeError(
                f"{state_paths[state_id]}: state crosses strategic regions "
                f"{sorted(state_region_ids)}"
            )
        state_regions[state_id] = next(iter(state_region_ids))

    continent_by_region: dict[int, int] = {}
    continent_by_state: dict[int, int] = {}
    manifest_keys: list[str] = []
    manifest_ids: set[int] = set()
    for entry in manifest["continents"]:
        if not isinstance(entry, dict):
            raise RuntimeError(f"{root / MANIFEST_RELATIVE}: continent entry must be an object")
        try:
            continent_id = int(entry["id"])
            key = str(entry["key"])
            strategic_region_ids = [int(value) for value in entry["strategic_regions"]]
            state_ids = [int(value) for value in entry["states"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"{root / MANIFEST_RELATIVE}: malformed continent entry") from exc
        if continent_id in manifest_ids:
            raise RuntimeError(f"{root / MANIFEST_RELATIVE}: duplicate continent {continent_id}")
        manifest_ids.add(continent_id)
        manifest_keys.append(key)
        for region_id in strategic_region_ids:
            if region_id not in regions:
                raise RuntimeError(f"manifest references unknown strategic region {region_id}")
            previous = continent_by_region.get(region_id)
            if previous is not None:
                raise RuntimeError(
                    f"strategic region {region_id} maps to continents {previous} and {continent_id}"
                )
            continent_by_region[region_id] = continent_id
        for state_id in state_ids:
            if state_id not in states:
                raise RuntimeError(f"manifest references unknown state {state_id}")
            previous = continent_by_state.get(state_id)
            if previous is not None:
                raise RuntimeError(
                    f"state {state_id} maps to continents {previous} and {continent_id}"
                )
            continent_by_state[state_id] = continent_id
    if manifest_ids != set(range(1, 8)):
        raise RuntimeError(f"manifest continent ids must be exactly 1..7, found {manifest_ids}")
    if tuple(manifest_keys) != continent_keys:
        raise RuntimeError(
            f"manifest keys {tuple(manifest_keys)} differ from {CONTINENT_RELATIVE} {continent_keys}"
        )

    fully_overridden = {
        int(value) for value in manifest.get("fully_overridden_strategic_regions", [])
    }
    unknown_fully_overridden = fully_overridden - set(regions)
    if unknown_fully_overridden:
        raise RuntimeError(
            f"manifest fully-overridden regions are unknown: {sorted(unknown_fully_overridden)}"
        )
    for state_id, region_id in state_regions.items():
        if region_id in fully_overridden and state_id not in continent_by_state:
            raise RuntimeError(
                f"state {state_id} in mixed strategic region {region_id} needs an explicit continent"
            )

    default_continent = int(manifest["default_continent"])
    state_continents = {
        state_id: continent_by_state.get(
            state_id, continent_by_region.get(region_id, default_continent)
        )
        for state_id, region_id in state_regions.items()
    }
    province_continents = {
        province: state_continents[state_by_province[province]] for province in real_land
    }
    state_counts = Counter(state_continents.values())
    province_counts = Counter(province_continents.values())
    if set(state_counts) != set(range(1, 8)) or set(province_counts) != set(range(1, 8)):
        raise RuntimeError(
            "every lore continent must contain states and land provinces; "
            f"states={dict(state_counts)}, provinces={dict(province_counts)}"
        )

    content = rewrite_continent_column(
        definition_source,
        province_continents,
        path=definition_path,
    )
    return TradeRegionPlan(
        content=content,
        continent_keys=continent_keys,
        state_continents=state_continents,
        state_regions=state_regions,
        province_continents=province_continents,
        state_counts=dict(state_counts),
        province_counts=dict(province_counts),
    )


def validate(root: Path = ROOT) -> list[str]:
    try:
        plan = build_plan(root)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return [str(exc)]
    path = root / DEFINITION_RELATIVE
    if path.read_bytes() != plan.content:
        return [
            f"{DEFINITION_RELATIVE.as_posix()}: lore continent column is stale; "
            "run python -B tools/build_adiscord_trade_regions.py --apply"
        ]
    return []


def apply(root: Path = ROOT) -> bool:
    plan = build_plan(root)
    path = root / DEFINITION_RELATIVE
    changed = path.read_bytes() != plan.content
    if changed:
        path.write_bytes(plan.content)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the lore-native trade-region continent column."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="write map/definition.csv; the default is a read-only check",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="explicitly run the read-only check (also the default)",
    )
    args = parser.parse_args(argv)

    if args.apply:
        try:
            changed = apply()
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print("Applied lore trade-region mapping." if changed else "Lore trade-region mapping already current.")

    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    plan = build_plan()
    counts = ", ".join(
        f"{continent_id}:{plan.province_counts[continent_id]}"
        for continent_id in range(1, 8)
    )
    print(f"Lore trade-region mapping passes ({counts} land provinces by continent).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
