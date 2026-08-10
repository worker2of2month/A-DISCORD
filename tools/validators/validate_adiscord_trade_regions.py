#!/usr/bin/env python3
"""Validate functional lore-native trade filtering in map/definition.csv."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from tools.builders.build_adiscord_trade_regions import (
    DEFINITION_RELATIVE,
    ROOT,
    build_plan,
)


EXPECTED_STATE_COUNTS = {1: 57, 2: 62, 3: 74, 4: 8, 5: 97, 6: 31, 7: 360}
EXPECTED_PROVINCE_COUNTS = {
    1: 607,
    2: 752,
    3: 923,
    4: 44,
    5: 1079,
    6: 419,
    7: 9560,
}

# These anchors prove that the mapping follows physical map regions rather
# than the country currently owning each state.
GEOGRAPHIC_STATE_ANCHORS = {
    66: (19, 2),   # Rus enclave lies in the Grey Belt / Exclusion Zone.
    78: (5, 7),    # The Danian expedition is in the far-west Outer Lands.
    120: (15, 1),  # ORV ownership does not move the Ainholm mandate eastward.
    141: (7, 6),   # Doln's western state remains in Western Forul.
    156: (21, 2),
    160: (21, 2),
    218: (23, 1),  # BTL enclave is an explicit Eastern Forul boundary override.
    223: (21, 2),
    461: (67, 2),  # Deliberately realigned Exclusion Zone fringe.
}


def validate(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    try:
        plan = build_plan(root)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        return [f"trade-region source model: {exc}"]

    definition_path = root / DEFINITION_RELATIVE
    if definition_path.read_bytes() != plan.content:
        issues.append(
            f"{DEFINITION_RELATIVE.as_posix()}: generated continent column is stale"
        )

    if dict(plan.state_counts) != EXPECTED_STATE_COUNTS:
        issues.append(
            "trade-region state geography drifted: "
            f"expected {EXPECTED_STATE_COUNTS}, found {dict(plan.state_counts)}"
        )
    if dict(plan.province_counts) != EXPECTED_PROVINCE_COUNTS:
        issues.append(
            "trade-region province geography drifted: "
            f"expected {EXPECTED_PROVINCE_COUNTS}, found {dict(plan.province_counts)}"
        )

    for state_id, (expected_region, expected_continent) in GEOGRAPHIC_STATE_ANCHORS.items():
        actual_region = plan.state_regions.get(state_id)
        actual_continent = plan.state_continents.get(state_id)
        if (actual_region, actual_continent) != (expected_region, expected_continent):
            issues.append(
                f"state {state_id}: expected strategic region {expected_region} and "
                f"continent {expected_continent}, found region {actual_region} and "
                f"continent {actual_continent}"
            )

    current_counts: Counter[int] = Counter()
    try:
        with definition_path.open(encoding="utf-8-sig", newline="") as source:
            for line_number, row in enumerate(csv.reader(source, delimiter=";"), 1):
                if len(row) != 8:
                    issues.append(
                        f"{DEFINITION_RELATIVE.as_posix()}:{line_number}: "
                        f"expected 8 fields, found {len(row)}"
                    )
                    continue
                province = int(row[0])
                province_type = row[4].strip().lower()
                continent = int(row[7])
                if province == 0:
                    if continent != 0:
                        issues.append("map/definition.csv: province 0 sentinel must use continent 0")
                elif province_type == "land":
                    if continent not in range(1, 8):
                        issues.append(
                            f"map/definition.csv:{line_number}: real land province {province} "
                            f"has invalid continent {continent}"
                        )
                    else:
                        current_counts[continent] += 1
                elif continent != 0:
                    issues.append(
                        f"map/definition.csv:{line_number}: {province_type} province {province} "
                        f"must use continent 0, found {continent}"
                    )
    except (OSError, UnicodeError, ValueError) as exc:
        issues.append(f"{DEFINITION_RELATIVE.as_posix()}: cannot validate rows: {exc}")

    if dict(current_counts) != EXPECTED_PROVINCE_COUNTS:
        issues.append(
            "map/definition.csv: current continent counts differ from the approved geography: "
            f"{dict(current_counts)}"
        )
    return issues


def main() -> int:
    issues = validate()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Lore trade-region geography and definition.csv continent mapping pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
