"""Planned province geography that the state-file owners take over.

The IVN geography builder records its second province plan under ``stage2`` in
``adiscord_ivn_provinces.json``; the east geography builder records its plans
in ``adiscord_mon_geography.json``: Stage 1 in ``planned``, Stage 2 in
``stage2.planned`` and every later stage as a record of the ``stages`` list,
in that order. A plan is recorded before its map apply, so its
ids are absent from ``definition.csv`` until then. Each stage reaches the map
as a whole: a stage is applied when all of its ids are defined, ignored when
none is, and a partly defined stage is an error.

Only the planned entries of applied stages are returned. Settlements and VP
overrides follow the states and regions those stages touch. A region's
``vp_overrides`` (``{province: value}``) may only name central-theatre VPs:
they redistribute points inside a theatre package.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .paths import repository_root


IVN_MANIFEST = Path("tools/data/adiscord_ivn_provinces.json")
EAST_GEOGRAPHY = Path("tools/data/adiscord_mon_geography.json")
DEFINITION = Path("map/definition.csv")
# Settlement kinds whose VP is a new objective; `adopt` reuses an existing city
# and its existing VP, and districts never hold one.
VP_SETTLEMENT_KINDS = frozenset({"city", "town", "village"})


@dataclass(frozen=True)
class PlannedProvince:
    province: int
    parent: int
    state: int
    kind: str
    source: str
    stage: str


@dataclass(frozen=True)
class PlannedSettlement:
    state: int
    kind: str
    province: int
    value: int
    name: str
    name_en: str
    source: str


@dataclass(frozen=True)
class PlannedGeography:
    provinces: tuple[PlannedProvince, ...] = ()
    settlements: tuple[PlannedSettlement, ...] = ()
    vp_overrides: Mapping[int, int] = field(default_factory=dict)

    def for_states(self, states: Iterable[int]) -> PlannedGeography:
        """Keep the provinces and settlements of `states`; overrides stay whole."""
        scope = frozenset(states)
        return PlannedGeography(
            tuple(entry for entry in self.provinces if entry.state in scope),
            tuple(entry for entry in self.settlements if entry.state in scope),
            self.vp_overrides,
        )

    def provinces_by_state(self) -> dict[int, frozenset[int]]:
        by_state: dict[int, set[int]] = {}
        for entry in self.provinces:
            by_state.setdefault(entry.state, set()).add(entry.province)
        return {state_id: frozenset(provinces) for state_id, provinces in by_state.items()}

    def vp_settlements(self) -> tuple[PlannedSettlement, ...]:
        return tuple(entry for entry in self.settlements if entry.kind in VP_SETTLEMENT_KINDS)

    def roots(self) -> dict[int, int]:
        return planned_roots(self.provinces)


def planned_roots(entries: Iterable[PlannedProvince]) -> dict[int, int]:
    """Map each planned province to the map province it was cut from.

    A later stage may cut a part from a planned remainder of an earlier one,
    so parents are followed until they leave the plan.
    """
    parents = {entry.province: entry.parent for entry in entries}
    roots: dict[int, int] = {}
    for province_id, parent in parents.items():
        root = parent
        visited = {province_id}
        while root in parents:
            if root in visited:
                raise RuntimeError(f"planned province {province_id} has a cyclic parent chain")
            visited.add(root)
            root = parents[root]
        roots[province_id] = root
    return roots


def east_stages(geography: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    """Return the east plans in map-apply order: `planned`, `stage2.planned`, then `stages`."""
    stages = []
    if geography.get("planned"):
        stages.append(geography["planned"])
    stage2 = geography.get("stage2", {}).get("planned")
    if stage2:
        stages.append(stage2)
    stages.extend(geography.get("stages", ()))
    return tuple(stages)


def east_stage_labels(stages: tuple[Mapping[str, object], ...]) -> tuple[str, ...]:
    """Name each plan by its recorded `stage` number, or by its position when it records none."""
    return tuple(f"East stage {stage.get('stage', number)}" for number, stage in enumerate(stages, start=1))


def ivn_stages(manifest: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    """Return the IVN plans not yet owned by the reviewed stage-1 tables."""
    stage2 = manifest.get("stage2")
    return (stage2,) if stage2 else ()


def stage_is_applied(stage: Mapping[str, object], label: str, defined: frozenset[int]) -> bool:
    planned = {int(entry["province"]) for entry in stage.get("provinces", ())}
    present = planned & defined
    if not present:
        return False
    if present != planned:
        missing = sorted(planned - present)
        raise RuntimeError(
            f"{label} province plan is only partly on the map: "
            f"{len(missing)} missing from {missing[0]}"
        )
    return True


def settlement_map(stages: Iterable[Mapping[str, object]], key: str) -> dict[int, int]:
    """Merge the `cities` or `towns` parent maps of the given stages."""
    merged: dict[int, int] = {}
    for stage in stages:
        for parent, province in stage.get(key, {}).items():
            merged[int(parent)] = int(province)
    return merged


def settlement_province(
    entry: Mapping[str, object], cities: Mapping[int, int], towns: Mapping[int, int]
) -> int | None:
    """Return the province that holds a settlement's VP, or None before it is chosen.

    An explicit `province` wins; otherwise the parent is resolved through the
    plan's city or town map, and a parent missing from the map keeps its id.
    """
    if entry.get("province") is not None:
        return int(entry["province"])
    if entry.get("parent") is None:
        return None
    parent = int(entry["parent"])
    lookup = towns if entry["kind"] in {"town", "village"} else cities
    return lookup.get(parent, parent)


def read_settlements(
    tables: Iterable[Iterable[Mapping[str, object]]],
    active_states: frozenset[int],
    cities: Mapping[int, int],
    towns: Mapping[int, int],
    source: str,
) -> list[PlannedSettlement]:
    settlements = []
    for table in tables:
        for entry in table:
            state_id = int(entry["state"])
            if entry["kind"] == "district" or state_id not in active_states:
                continue
            province_id = settlement_province(entry, cities, towns)
            if province_id is None:
                continue
            settlements.append(
                PlannedSettlement(
                    state=state_id,
                    kind=str(entry["kind"]),
                    province=province_id,
                    value=int(entry.get("value", 0)),
                    name=str(entry.get("name", "")),
                    name_en=str(entry.get("name_en", "")),
                    source=source,
                )
            )
    return settlements


def read_source(
    stages: tuple[Mapping[str, object], ...],
    labels: tuple[str, ...],
    defined: frozenset[int],
    source: str,
) -> tuple[list[PlannedProvince], list[Mapping[str, object]]]:
    provinces = []
    applied = []
    for stage, label in zip(stages, labels):
        if not stage_is_applied(stage, label, defined):
            continue
        applied.append(stage)
        provinces.extend(
            PlannedProvince(
                province=int(entry["province"]),
                parent=int(entry["parent"]),
                state=int(entry["state"]),
                kind=str(entry["kind"]),
                source=source,
                stage=label,
            )
            for entry in stage["provinces"]
        )
    return provinces, applied


def ivn_planned_geography(
    manifest: Mapping[str, object], defined: frozenset[int]
) -> tuple[list[PlannedProvince], list[PlannedSettlement]]:
    stages = ivn_stages(manifest)
    provinces, applied = read_source(stages, ("IVN stage 2",), defined, "ivn")
    active_states = frozenset(entry.state for entry in provinces)
    settlements = read_settlements(
        (stage.get("settlements", ()) for stage in applied),
        active_states,
        settlement_map(applied, "cities"),
        settlement_map(applied, "towns"),
        "ivn",
    )
    return provinces, settlements


def east_planned_geography(
    geography: Mapping[str, object], defined: frozenset[int]
) -> tuple[list[PlannedProvince], list[PlannedSettlement], dict[int, int]]:
    stages = east_stages(geography)
    provinces, applied = read_source(stages, east_stage_labels(stages), defined, "east")
    active_states = frozenset(entry.state for entry in provinces)
    regions = tuple(geography.get("regions", {}).values())
    tables = (
        geography.get("settlements", ()),
        geography.get("stage2", {}).get("settlements", ()),
        *(stage.get("settlements", ()) for stage in stages),
        *(region.get("settlements", ()) for region in regions),
    )
    settlements = read_settlements(
        tables,
        active_states,
        settlement_map(applied, "cities"),
        settlement_map(applied, "towns"),
        "east",
    )
    overrides: dict[int, int] = {}
    for region in regions:
        if not active_states & {int(state_id) for state_id in region.get("states", ())}:
            continue
        for province, value in region.get("vp_overrides", {}).items():
            if int(province) in overrides:
                raise RuntimeError(f"VP override {province} appears in more than one region")
            overrides[int(province)] = int(value)
    return provinces, settlements, overrides


def planned_geography(
    ivn_manifest: Mapping[str, object],
    east_geography: Mapping[str, object],
    defined: Iterable[int],
) -> PlannedGeography:
    """Combine the applied IVN and east plans; ids may appear in one entry only."""
    defined_ids = frozenset(defined)
    ivn_provinces, ivn_settlements = ivn_planned_geography(ivn_manifest, defined_ids)
    east_provinces, east_settlements, overrides = east_planned_geography(east_geography, defined_ids)
    provinces = (*ivn_provinces, *east_provinces)
    seen: set[int] = set()
    for entry in provinces:
        if entry.province in seen:
            raise RuntimeError(f"planned province {entry.province} appears in more than one plan entry")
        seen.add(entry.province)
    settlements: dict[int, PlannedSettlement] = {}
    for entry in (*ivn_settlements, *east_settlements):
        if entry.province in settlements and settlements[entry.province] != entry:
            raise RuntimeError(f"planned settlement {entry.province} is declared twice")
        settlements[entry.province] = entry
    return PlannedGeography(tuple(provinces), tuple(settlements.values()), overrides)


def defined_provinces(root: Path) -> frozenset[int]:
    return frozenset(
        int(row[0])
        for line in (root / DEFINITION).read_text(encoding="utf-8-sig").splitlines()
        if (row := line.split(";"))[0].isdigit()
    )


@lru_cache(maxsize=None)
def load_planned_geography(root: Path | None = None) -> PlannedGeography:
    base = root or repository_root()
    return planned_geography(
        json.loads((base / IVN_MANIFEST).read_text(encoding="utf-8")),
        json.loads((base / EAST_GEOGRAPHY).read_text(encoding="utf-8")),
        defined_provinces(base),
    )
