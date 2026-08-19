"""Province adjacency and connected-channel helpers for the map network layers.

``map/railways.txt`` is an ordered province sequence per line and ``map/rivers.bmp``
is a one-pixel channel raster, and both are only meaningful against the province
polygons in ``map/provinces.bmp``.  A railway whose consecutive provinces do not
share a border is a supply route the engine cannot follow, and a river only
produces a river-crossing combat penalty where it lies *between* two provinces
rather than inside one.  Both questions therefore reduce to the same two
primitives: which provinces touch, and where the borders are.

This module owns no output.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

from tools.lib import map_relief as relief_math
from tools.lib.map_raster import DefinitionRow


# ``map/rivers.bmp`` reserves 0 for a source marker, 1 and 2 for flow direction
# and 3..11 for channel widths; 254 is land background and 255 is sea.
RIVER_SOURCE = 0
RIVER_FLOW_IN = 1
RIVER_FLOW_OUT = 2
RIVER_CHANNEL_MAX = 11
RIVER_LAND_BACKGROUND = 254
RIVER_SEA_BACKGROUND = 255
RIVER_VALID_INDICES = frozenset(
    set(range(0, RIVER_CHANNEL_MAX + 1)) | {RIVER_LAND_BACKGROUND, RIVER_SEA_BACKGROUND}
)


def province_id_field(
    provinces: np.ndarray, definition: Mapping[int, DefinitionRow]
) -> np.ndarray:
    """Return the province id of every pixel, or ``0`` where the colour is unknown.

    ``0`` is safe as the sentinel because HOI4 province ids start at 1.
    """

    packed = relief_math.packed_colours(provinces)
    colours: list[int] = []
    identifiers: list[int] = []
    for province_id, row in definition.items():
        red, green, blue = row.color
        colours.append((red << 16) | (green << 8) | blue)
        identifiers.append(province_id)
    codes = relief_math.map_colours_to_codes(packed, colours, identifiers, 0)
    return codes.astype(np.int32)


def raster_adjacency(field: np.ndarray) -> dict[int, set[int]]:
    """Return the 4-connected shared-border graph of ``field``.

    Diagonal touches are excluded deliberately: HOI4 treats a shared *edge* as
    adjacency, and admitting corner contact would declare pairs adjacent that the
    engine will not move an army or a train between.
    """

    adjacency: dict[int, set[int]] = {}
    for first, second in (
        (field[:, :-1], field[:, 1:]),
        (field[:-1, :], field[1:, :]),
    ):
        differing = (first != second) & (first > 0) & (second > 0)
        for left, right in zip(first[differing].tolist(), second[differing].tolist()):
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)
    return adjacency


def declared_adjacencies(path: Path) -> set[tuple[int, int]]:
    """Return the explicit province pairs from ``map/adjacencies.csv``.

    Rows with a negative id are the file's terminator convention and rows whose
    first field is not numeric are its header or comments; both are skipped.
    """

    pairs: set[tuple[int, int]] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = line.split(";")
        if len(fields) < 2:
            continue
        try:
            first = int(fields[0])
            second = int(fields[1])
        except ValueError:
            continue
        if first <= 0 or second <= 0:
            continue
        pairs.add((min(first, second), max(first, second)))
    return pairs


class ProvinceGraph:
    """Shared-border adjacency, plus the explicit pairs from adjacencies.csv."""

    def __init__(
        self,
        field: np.ndarray,
        definition: Mapping[int, DefinitionRow],
        declared: Iterable[tuple[int, int]] = (),
    ) -> None:
        self.field = field
        self.definition = definition
        self.adjacency = raster_adjacency(field)
        self.declared = set(declared)
        for first, second in self.declared:
            self.adjacency.setdefault(first, set()).add(second)
            self.adjacency.setdefault(second, set()).add(first)
        self.present = frozenset(int(value) for value in np.unique(field) if value > 0)

    def linked(self, first: int, second: int) -> bool:
        return second in self.adjacency.get(first, ())

    def is_land(self, province_id: int) -> bool:
        row = self.definition.get(province_id)
        return row is not None and row.is_land

    def shortest_land_path(
        self, start: int, goal: int, limit: int = 8
    ) -> list[int] | None:
        """Return the shortest all-land province path strictly between two ids.

        Used to propose a repair for a broken railway: the missing stops are the
        interior of this path.  ``limit`` bounds the search so a genuinely
        unreachable pair returns ``None`` instead of walking the whole continent -
        a twenty-province detour is not a lost intermediate stop, it is a
        different route, and inventing one would silently change supply.
        """

        if start == goal:
            return []
        seen = {start}
        frontier: deque[tuple[int, list[int]]] = deque([(start, [])])
        while frontier:
            current, path = frontier.popleft()
            if len(path) >= limit:
                continue
            for neighbour in sorted(self.adjacency.get(current, ())):
                if neighbour == goal:
                    return path
                if neighbour in seen or not self.is_land(neighbour):
                    continue
                seen.add(neighbour)
                frontier.append((neighbour, [*path, neighbour]))
        return None

    def border_mask(self) -> np.ndarray:
        """Return the land pixels that sit on a boundary between two provinces.

        Sliced rather than rolled, so the raster edges do not wrap.  A rolled
        comparison marks the first column as bordering the last and the top row as
        bordering the bottom, which would report the polar rows as a province
        boundary and quietly inflate the river alignment score.
        """

        border = np.zeros(self.field.shape, dtype=bool)
        for first, second, into_first, into_second in (
            (
                self.field[:, :-1],
                self.field[:, 1:],
                (slice(None), slice(None, -1)),
                (slice(None), slice(1, None)),
            ),
            (
                self.field[:-1, :],
                self.field[1:, :],
                (slice(None, -1), slice(None)),
                (slice(1, None), slice(None)),
            ),
        ):
            differing = (first != second) & (first > 0) & (second > 0)
            border[into_first] |= differing
            border[into_second] |= differing
        return border


def province_median_heights(
    field: np.ndarray, heights: np.ndarray, wanted: Iterable[int]
) -> dict[int, float]:
    """Return the median elevation of each requested province.

    The median rather than the mean, so a single carved river pixel or a levelled
    city pad cannot drag a province's reported elevation off its real ground.
    """

    result: dict[int, float] = {}
    for province_id in sorted(set(wanted)):
        selected = field == province_id
        if selected.any():
            result[province_id] = float(np.median(heights[selected]))
    return result


def connected_systems(channel: np.ndarray) -> list[np.ndarray]:
    """Return the 8-connected pixel-index groups of a river channel mask.

    Eight-connected because HOI4 river channels are one pixel wide and turn
    diagonally; treating a diagonal step as a break would split every bend into
    its own system.
    """

    height, width = channel.shape
    flat = channel.reshape(-1)
    labels = np.zeros(flat.size, dtype=np.int32)
    offsets = (-width - 1, -width, -width + 1, -1, 1, width - 1, width, width + 1)
    systems: list[np.ndarray] = []
    for seed in np.flatnonzero(flat).tolist():
        if labels[seed]:
            continue
        label = len(systems) + 1
        labels[seed] = label
        stack = [seed]
        members: list[int] = []
        while stack:
            index = stack.pop()
            members.append(index)
            column = index % width
            for offset in offsets:
                neighbour = index + offset
                if neighbour < 0 or neighbour >= flat.size:
                    continue
                if abs((neighbour % width) - column) > 1:
                    continue
                if flat[neighbour] and not labels[neighbour]:
                    labels[neighbour] = label
                    stack.append(neighbour)
        systems.append(np.array(sorted(members), dtype=np.int64))
    return systems


def parse_railways(path: Path) -> list[tuple[int, int, int, list[int]]]:
    """Parse ``map/railways.txt`` into ``(line number, level, declared, path)``.

    The declared count is kept separate from the parsed path on purpose: a line
    whose count disagrees with its province list is a defect the engine reads
    silently, so the validator has to see both numbers.
    """

    railways: list[tuple[int, int, int, list[int]]] = []
    for number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        fields = line.split()
        if not fields:
            continue
        if len(fields) < 3:
            raise RuntimeError(f"map/railways.txt line {number}: too few fields")
        try:
            values = [int(field) for field in fields]
        except ValueError as error:
            raise RuntimeError(
                f"map/railways.txt line {number}: non-numeric field"
            ) from error
        railways.append((number, values[0], values[1], values[2:]))
    return railways


def path_relief(
    provinces: Sequence[int], medians: Mapping[int, float]
) -> tuple[float, float]:
    """Return ``(worst single step, total climb)`` in height units along a path."""

    worst = 0.0
    total = 0.0
    for first, second in zip(provinces, provinces[1:]):
        if first in medians and second in medians:
            step = abs(medians[second] - medians[first])
            worst = max(worst, step)
            total += step
    return worst, total
