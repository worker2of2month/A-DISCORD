#!/usr/bin/env python3
"""Validate ``map/rivers.bmp`` format, topology and province-border alignment.

Two separate things matter about a HOI4 river and they are easy to confuse.

The *format* is strict and unforgiving: the channel is one pixel wide, palette 0
marks a source, 1 and 2 mark flow direction, 3 to 11 are channel widths, and 254
and 255 are the land and sea backgrounds.  Any other index, or a connected system
without exactly one source, makes the engine complain at load time or draw the
river wrongly.  Those are hard failures here.

The *alignment* is a gameplay question.  A river only produces a river-crossing
combat penalty where it lies on the border *between* two provinces; a channel
through a province interior is purely decorative.  So border-aligned rivers are
the correct target - but moving a channel onto a border *creates* a crossing
penalty that did not exist before, which changes combat balance.  This validator
therefore measures alignment and refuses to let it get worse; it does not demand
perfection, and it deliberately does not reroute anything.

The measurement is the reason no rerouting happened: 97.0% of channel pixels
already sit exactly on a province border and 98.0% are within one pixel, so the
interior tail is 776 pixels spread over a handful of short systems.  Rerouting
map-wide to chase that would move far more combat modifiers than it fixed.  The
per-system numbers are recorded in
``tools/data/adiscord_map_river_findings.json`` so the tail stays visible.

Nothing here writes any file.
"""

from __future__ import annotations

import argparse
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from tools.lib import map_relief as relief_math
from tools.lib.map_network import (
    ProvinceGraph,
    RIVER_CHANNEL_MAX,
    RIVER_SOURCE,
    RIVER_VALID_INDICES,
    connected_systems,
    declared_adjacencies,
    province_id_field,
)
from tools.lib.map_raster import read_definition


ROOT = Path(__file__).resolve().parents[2]
RIVERS_PATH = ROOT / "map" / "rivers.bmp"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
ADJACENCIES_PATH = ROOT / "map" / "adjacencies.csv"
FINDINGS_PATH = ROOT / "tools" / "data" / "adiscord_map_river_findings.json"

# Systems below this size are single stubs and short spurs; their source markers
# and interior depth are noise rather than signal.
MIN_REPORTED_SYSTEM = 40
# How far the distance transform looks before saturating.  A channel more than
# this far from any border is deep interior by any measure.
BORDER_DISTANCE_LIMIT = 24
# Tolerance on the recorded alignment share, in percentage points.  A repaint of
# the relief can shift a handful of pixels without the rivers having moved.
ALIGNMENT_TOLERANCE = 0.005


def _load() -> tuple[np.ndarray, np.ndarray, ProvinceGraph]:
    definition = read_definition(DEFINITION_PATH)
    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces:
        field = province_id_field(
            np.asarray(provinces.convert("RGB"), dtype=np.uint8), definition
        )
        size = provinces.size
    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as rivers:
        if rivers.mode != "P":
            raise RuntimeError(f"map/rivers.bmp must stay paletted, found {rivers.mode}")
        if rivers.size != size:
            raise RuntimeError("map/rivers.bmp and map/provinces.bmp differ in size")
        channel_values = np.asarray(rivers, dtype=np.uint8).copy()
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as heightmap:
        heights = np.asarray(heightmap, dtype=np.uint8).copy()
    graph = ProvinceGraph(field, definition, declared_adjacencies(ADJACENCIES_PATH))
    return channel_values, heights, graph


def load_findings() -> dict[str, object]:
    payload = json.loads(FINDINGS_PATH.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise RuntimeError("river findings schema must be 1")
    return payload


def audit() -> tuple[list[str], dict[str, object]]:
    """Return ``(format issues, report)`` for the current river layer."""

    values, heights, graph = _load()
    issues: list[str] = []

    unknown = sorted(set(np.unique(values).tolist()) - RIVER_VALID_INDICES)
    if unknown:
        issues.append(
            f"map/rivers.bmp: palette indices {unknown} are not source, flow, "
            f"width 3..{RIVER_CHANNEL_MAX} or a background value"
        )

    channel = values <= RIVER_CHANNEL_MAX
    border = graph.border_mask()
    # ``edge_distance`` erodes the *complement* of the border, so a channel pixel
    # standing on a border scores zero and one deep in an interior scores its true
    # distance, saturating at the limit.
    depth = np.where(border, 0, relief_math.edge_distance(~border, BORDER_DISTANCE_LIMIT))
    channel_depth = depth[channel]
    total = int(channel.sum())
    if not total:
        issues.append("map/rivers.bmp: no channel pixels at all")
        return issues, {"schema": 1, "channel_pixels": 0}

    systems = connected_systems(channel)
    flat_values = values.reshape(-1)
    flat_depth = depth.reshape(-1)
    flat_heights = heights.reshape(-1)
    width = values.shape[1]

    multi_source: list[int] = []
    no_source: list[int] = []
    rows: list[dict[str, object]] = []
    for members in systems:
        sources = int((flat_values[members] == RIVER_SOURCE).sum())
        if len(members) >= MIN_REPORTED_SYSTEM:
            depths = flat_depth[members]
            elevations = flat_heights[members]
            seed = int(members[0])
            rows.append(
                {
                    "size": int(members.size),
                    "sources": sources,
                    "mean_border_depth": round(float(depths.mean()), 3),
                    "max_border_depth": int(depths.max()),
                    "height_span": int(elevations.max()) - int(elevations.min()),
                    "x": seed % width,
                    "y": seed // width,
                }
            )
        if len(members) >= 8:
            if sources == 0:
                no_source.append(int(members[0]))
            elif sources > 1:
                multi_source.append(int(members[0]))

    rows.sort(key=lambda row: (-float(row["mean_border_depth"]), -int(row["size"])))
    report = {
        "schema": 1,
        "channel_pixels": total,
        "on_border_share": round(float((channel_depth == 0).mean()), 4),
        "within_one_pixel_share": round(float((channel_depth <= 1).mean()), 4),
        "interior_pixels": int((channel_depth > 1).sum()),
        "max_border_depth": int(channel_depth.max()),
        "systems": len(systems),
        "systems_without_source": no_source,
        "systems_with_extra_sources": multi_source,
        "worst_systems": rows[:20],
    }
    return issues, report


def validate() -> list[str]:
    issues, report = audit()
    if not report.get("channel_pixels"):
        return issues
    recorded = load_findings()

    for key, label in (
        ("on_border_share", "channel pixels sitting exactly on a province border"),
        ("within_one_pixel_share", "channel pixels within one pixel of a border"),
    ):
        found = float(report[key])
        floor = float(recorded[key]) - ALIGNMENT_TOLERANCE  # type: ignore[arg-type]
        if found < floor:
            issues.append(
                f"map/rivers.bmp: only {found:.1%} of {label}, below the recorded "
                f"{float(recorded[key]):.1%}; a channel has moved off the borders "  # type: ignore[arg-type]
                "and lost its river-crossing penalty"
            )
    ceiling = int(recorded["interior_pixels"])  # type: ignore[arg-type]
    if int(report["interior_pixels"]) > ceiling:
        issues.append(
            f"map/rivers.bmp: {report['interior_pixels']} channel pixels now lie more "
            f"than one pixel inside a province, above the recorded {ceiling}"
        )
    if report["systems_without_source"] != recorded["systems_without_source"]:
        issues.append(
            "map/rivers.bmp: the set of river systems lacking a source marker changed; "
            "every connected system needs exactly one palette-0 source or the engine "
            "draws it wrongly"
        )
    if len(report["systems_with_extra_sources"]) > len(  # type: ignore[arg-type]
        recorded["systems_with_extra_sources"]  # type: ignore[arg-type]
    ):
        issues.append(
            "map/rivers.bmp: a river system gained a second source marker"
        )
    return issues


def _report(report: dict[str, object]) -> None:
    print(
        f"River audit: {report['channel_pixels']} channel pixels in "
        f"{report['systems']} connected systems."
    )
    print(
        f"  on a province border      {float(report['on_border_share']):.1%}\n"
        f"  within one pixel of one   {float(report['within_one_pixel_share']):.1%}\n"
        f"  deeper than one pixel     {report['interior_pixels']} pixels "
        f"(worst {report['max_border_depth']} px from any border)"
    )
    extra = report["systems_with_extra_sources"]
    missing = report["systems_without_source"]
    print(f"  systems with no source    {len(missing)}")
    print(f"  systems with extra source {len(extra)}")
    print("  worst systems by mean distance from a province border:")
    for row in report["worst_systems"][:10]:  # type: ignore[index]
        print(
            f"    size {row['size']:5d} at x={row['x']:4d} y={row['y']:4d}: "
            f"mean {float(row['mean_border_depth']):5.2f} px, max "
            f"{row['max_border_depth']:2d} px, channel height span "
            f"{row['height_span']:3d}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check", action="store_true", help="validate the river layer (default)"
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
    print("River layer validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
