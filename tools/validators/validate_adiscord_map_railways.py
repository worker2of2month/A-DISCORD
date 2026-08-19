#!/usr/bin/env python3
"""Validate ``map/railways.txt`` against the province polygons and the relief.

A railway in HOI4 is a level followed by an ordered province sequence, and the
engine walks that sequence literally.  If two consecutive provinces do not share
a border the line is not a shortcut, it is a *break*: supply stops flowing along
it and nothing in the game tells you so.  Nothing in this repository checked that
until now, and the audit this validator automates found twelve such breaks across
ten lines - the "они могли оборваться давно" the map owner suspected.

The validator therefore asserts four things.  Every referenced province must
exist in ``map/definition.csv``, must actually appear in ``map/provinces.bmp``,
and must be land.  Every declared count must match its province list.  Every
level must be one the engine accepts.  And every consecutive pair must share a
border in the raster or be joined explicitly by ``map/adjacencies.csv``.

The twelve breaks that already exist are recorded in
``tools/data/adiscord_map_railway_findings.json`` rather than silently tolerated.
Repairing one means inserting the missing intermediate provinces, and that
changes which provinces a supply line runs through - a gameplay decision that is
not this validator's to make.  Recording them keeps the tail visible and makes
this a guard against *new* breakage: an unrecorded break fails the run, and a
recorded one that has been repaired fails it too, so the file cannot rot in
either direction.

Nothing here writes any file.  ``map/railways.txt`` is generated output owned by
:mod:`tools.builders.build_adiscord_vorkerland_theatre`; a repair belongs in that
builder.
"""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from tools.lib.map_network import (
    ProvinceGraph,
    declared_adjacencies,
    parse_railways,
    path_relief,
    province_id_field,
    province_median_heights,
)
from tools.lib.map_raster import read_definition


ROOT = Path(__file__).resolve().parents[2]
RAILWAYS_PATH = ROOT / "map" / "railways.txt"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
ADJACENCIES_PATH = ROOT / "map" / "adjacencies.csv"
FINDINGS_PATH = ROOT / "tools" / "data" / "adiscord_map_railway_findings.json"

# HOI4 accepts railway levels 1..5; anything else is silently dropped.
MIN_LEVEL = 1
MAX_LEVEL = 5
# A railway of one province cannot carry supply anywhere.
MIN_PROVINCES = 2
# How far the repair search may look for missing intermediate stops.  Beyond this
# a "gap" is a different route rather than a lost stop, and proposing one would
# quietly redirect supply.
REPAIR_SEARCH_LIMIT = 8


def _load() -> tuple[ProvinceGraph, np.ndarray, list[tuple[int, int, int, list[int]]]]:
    definition = read_definition(DEFINITION_PATH)
    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces:
        field = province_id_field(
            np.asarray(provinces.convert("RGB"), dtype=np.uint8), definition
        )
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as heightmap:
        heights = np.asarray(heightmap, dtype=np.uint8).copy()
    if heights.shape != field.shape:
        raise RuntimeError("map/heightmap.bmp and map/provinces.bmp differ in size")
    graph = ProvinceGraph(field, definition, declared_adjacencies(ADJACENCIES_PATH))
    return graph, heights, parse_railways(RAILWAYS_PATH)


def load_findings() -> dict[str, object]:
    payload = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise RuntimeError("railway findings schema must be 1")
    return payload


def known_breaks(payload: dict[str, object]) -> set[tuple[int, int, int]]:
    return {
        (int(entry["line"]), int(entry["from"]), int(entry["to"]))
        for entry in payload["adjacency_breaks"]  # type: ignore[index]
    }


def audit() -> tuple[list[str], dict[str, object]]:
    """Return ``(issues, report)`` for the current railway network."""

    graph, heights, railways = _load()
    issues: list[str] = []
    breaks: list[dict[str, object]] = []
    referenced = {pid for _n, _l, _c, path in railways for pid in path}
    medians = province_median_heights(graph.field, heights, referenced)

    for number, level, declared, path in railways:
        label = f"map/railways.txt line {number}"
        if not MIN_LEVEL <= level <= MAX_LEVEL:
            issues.append(f"{label}: level {level} is outside {MIN_LEVEL}..{MAX_LEVEL}")
        if declared != len(path):
            issues.append(
                f"{label}: declares {declared} provinces but lists {len(path)}"
            )
        if len(path) < MIN_PROVINCES:
            issues.append(f"{label}: only {len(path)} province(s), so it carries nothing")
        for province_id in path:
            if province_id not in graph.definition:
                issues.append(f"{label}: province {province_id} is not in definition.csv")
            elif province_id not in graph.present:
                issues.append(
                    f"{label}: province {province_id} has no pixels in provinces.bmp"
                )
            elif not graph.is_land(province_id):
                issues.append(
                    f"{label}: province {province_id} is "
                    f"{graph.definition[province_id].kind}, so a railway cannot run there"
                )
        for first, second in zip(path, path[1:]):
            if first == second:
                issues.append(f"{label}: repeats province {first} consecutively")
                continue
            if first not in graph.definition or second not in graph.definition:
                continue
            if graph.linked(first, second):
                continue
            repair = graph.shortest_land_path(first, second, REPAIR_SEARCH_LIMIT)
            breaks.append(
                {
                    "line": number,
                    "from": first,
                    "to": second,
                    "missing_provinces": repair,
                    "repairable": repair is not None,
                }
            )

    relief_rows = []
    for number, level, _declared, path in railways:
        worst, total = path_relief(path, medians)
        mountains = [
            province_id
            for province_id in path
            if graph.definition.get(province_id) is not None
            and graph.definition[province_id].terrain == "mountain"
        ]
        relief_rows.append(
            {
                "line": number,
                "level": level,
                "provinces": len(path),
                "worst_step": round(worst, 1),
                "total_climb": round(total, 1),
                "mountain_provinces": mountains,
            }
        )
    report = {
        "schema": 1,
        "railways": len(railways),
        "referenced_provinces": len(referenced),
        "adjacency_breaks": breaks,
        "relief": relief_rows,
    }
    return issues, report


def validate() -> list[str]:
    issues, report = audit()
    recorded = load_findings()
    expected = known_breaks(recorded)
    found = {
        (int(entry["line"]), int(entry["from"]), int(entry["to"]))
        for entry in report["adjacency_breaks"]  # type: ignore[index]
    }
    for line, first, second in sorted(found - expected):
        issues.append(
            f"map/railways.txt line {line}: {first} -> {second} do not share a border "
            "and the break is not recorded in "
            "tools/data/adiscord_map_railway_findings.json"
        )
    for line, first, second in sorted(expected - found):
        issues.append(
            f"tools/data/adiscord_map_railway_findings.json records a break at line "
            f"{line} ({first} -> {second}) that no longer exists; remove the entry"
        )
    worst_recorded = float(recorded["max_recorded_worst_step"])  # type: ignore[index]
    worst_found = max(
        (float(row["worst_step"]) for row in report["relief"]),  # type: ignore[index]
        default=0.0,
    )
    if worst_found > worst_recorded:
        issues.append(
            f"map/railways.txt: a railway now climbs {worst_found:.1f} height units "
            f"between consecutive provinces, above the recorded "
            f"{worst_recorded:.1f}; carve a pass along the line rather than rerouting it"
        )
    return issues


def _report(report: dict[str, object]) -> None:
    breaks = report["adjacency_breaks"]  # type: ignore[index]
    print(
        f"Railway audit: {report['railways']} lines over "
        f"{report['referenced_provinces']} provinces, {len(breaks)} adjacency break(s)."
    )
    for entry in breaks:  # type: ignore[union-attr]
        missing = entry["missing_provinces"]
        if missing is None:
            detail = "no all-land path found within the search limit"
        elif missing:
            detail = "insert " + " ".join(str(value) for value in missing)
        else:
            detail = "adjacent through an explicit adjacency only"
        print(
            f"  line {entry['line']:3d}: {entry['from']} -> {entry['to']}  ({detail})"
        )
    steep = sorted(
        report["relief"],  # type: ignore[index,arg-type]
        key=lambda row: -float(row["worst_step"]),
    )[:10]
    print("Steepest railways (median province elevation, height units):")
    for row in steep:
        mountains = row["mountain_provinces"]
        suffix = f"  mountain provinces {mountains}" if mountains else ""
        print(
            f"  line {row['line']:3d} level {row['level']} "
            f"{row['provinces']:2d} provinces: worst step {row['worst_step']:5.1f}, "
            f"total climb {row['total_climb']:6.1f}{suffix}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check", action="store_true", help="validate the railway network (default)"
    )
    action.add_argument(
        "--report", action="store_true", help="print the full audit and exit 0"
    )
    args = parser.parse_args()
    _issues, report = audit()
    _report(report)
    if args.report:
        return 0
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Railway network validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
