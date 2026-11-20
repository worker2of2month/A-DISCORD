"""Report potential wiring conflicts in the NAM corporate focus tree without editing it.

Run from the mod root with python -B -m tools.validators.inspect_nam_corporate_focus_layout.
The report models the inter-row wiring at the current GUI grid spacing. Inspect
reported contacts in game to account for zoom, arrow sprites and shared trunks.
"""

import argparse
from itertools import combinations
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


SOURCE = Path(__file__).resolve().parents[2] / "focus_trees/NAM/exile_corporate/focuses.txt"


def corporate_focus_wiring(positions, prerequisites, exclusions):
    """Inspect the native inter-row trunks in half-row units, including corner contacts."""
    issues = {"card_spacing": [], "card_hits": [], "crossings": []}
    for (a, (ax, ay)), (b, (bx, by)) in combinations(positions.items(), 2):
        if ay == by and abs(ax - bx) < 2:
            issues["card_spacing"].append((a, b))
    centers = {name: (x, 2 * y) for name, (x, y) in positions.items()}
    wires = []
    for a, b in prerequisites:
        ax, ay = centers[a]
        bx, by = centers[b]
        # HOI4 runs sideways beneath the parent, then down the child's column.
        # All elbows, junctions and card centres are integral on this grid.
        bus = ay + 1
        trace = {(ax, ay), (ax, bus)}
        trace.update((x, bus) for x in range(min(ax, bx), max(ax, bx) + 1))
        trace.update((bx, y) for y in range(min(bus, by), max(bus, by) + 1))
        wires.append((a, b, trace))
    for a, b in exclusions:
        ax, ay = centers[a]
        bx, by = centers[b]
        if ay != by:
            issues.setdefault("unmodelled_exclusions", []).append((a, b))
            continue
        wires.append((a, b, {(x, ay) for x in range(min(ax, bx), max(ax, bx) + 1)}))
    for a, b, trace in wires:
        for name, point in centers.items():
            if name not in (a, b) and point in trace:
                issues["card_hits"].append((a, b, name))
    for (a, b, first), (c, d, second) in combinations(wires, 2):
        if a in (c, d) or b in (c, d):
            continue
        contact = first & second
        if contact:
            issues["crossings"].append(((a, b), (c, d), min(contact)))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details", action="store_true", help="List every pair of affected focus IDs")
    args = parser.parse_args()
    entries = parse_clausewitz(SOURCE.read_text(encoding="utf-8-sig"))
    tree = next(entry.value for entry in entries if entry.key == "focus_tree")
    positions = {}
    parents = {}
    prerequisites = []
    exclusions = set()
    for entry in tree:
        if entry.key != "focus":
            continue
        body = entry.value
        fields = {field.key: field.value for field in body}
        name = fields["id"]
        if "offset" in fields or "allow_branch" in fields:
            parser.error(f"{name} has conditional positioning or visibility; inspect its active layout in game")
        positions[name] = (int(fields.get("x", 0)), int(fields.get("y", 0)))
        parents[name] = fields.get("relative_position_id")
        for group in body:
            if group.key == "prerequisite":
                prerequisites.extend((item.value, name) for item in group.value if item.key == "focus")
            elif group.key == "mutually_exclusive":
                exclusions.update(tuple(sorted((name, item.value))) for item in group.value if item.key == "focus")
    for name in positions:
        parent = parents[name]
        chain = {name}
        x, y = positions[name]
        while parent:
            if parent in chain or parent not in positions:
                parser.error(f"Invalid relative position for {name} at {parent}")
            chain.add(parent)
            dx, dy = positions[parent]
            x += dx
            y += dy
            parent = parents[parent]
        positions[name] = (x, y)
        parents[name] = None
    for kind, contacts in corporate_focus_wiring(positions, prerequisites, sorted(exclusions)).items():
        print(f"{kind}: {len(contacts)}")
        if args.details:
            for contact in contacts:
                print(" ", contact)


if __name__ == "__main__":
    main()
