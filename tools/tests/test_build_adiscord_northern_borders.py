from __future__ import annotations

from array import array
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.builders import build_adiscord_northern_borders as builder


def _info(province_id: int, rgb: tuple[int, int, int], kind: str = "land") -> builder.ProvinceInfo:
    return builder.ProvinceInfo(
        province_id=province_id,
        color=builder.pack_rgb(*rgb),
        rgb=rgb,
        kind=kind,
        coastal=kind != "land",
        terrain="plains" if kind == "land" else "ocean",
        continent="1",
    )


def _state_from_grid(grid: list[list[int]], kinds: dict[int, str], owners: dict[int, str]) -> builder.BorderState:
    height = len(grid)
    width = len(grid[0])
    palette = {
        1: (10, 20, 30),
        2: (40, 50, 60),
        8: (0, 0, 80),
        9: (0, 0, 120),
    }
    by_id = {
        province_id: _info(province_id, rgb, kinds.get(province_id, "land"))
        for province_id, rgb in palette.items()
    }
    colors = array("I", [0]) * (width * height)
    province_ids = array("I", [0]) * (width * height)
    land = bytearray(width * height)
    counts: dict[int, int] = {}
    for y, row in enumerate(grid):
        for x, province_id in enumerate(row):
            index = y * width + x
            info = by_id[province_id]
            colors[index] = info.color
            province_ids[index] = province_id
            land[index] = 1 if info.kind == "land" else 0
            counts[province_id] = counts.get(province_id, 0) + 1
    return builder.BorderState(
        width=width,
        height=height,
        colors=colors,
        province_ids=province_ids,
        land=land,
        blocked=bytearray(width * height),
        owners=owners,
        by_id=by_id,
        counts=counts,
    )


class NorthernBorderBuilderTests(unittest.TestCase):
    def test_pack_rgb_round_trip(self) -> None:
        self.assertEqual(builder.unpack_rgb(builder.pack_rgb(12, 34, 56)), (12, 34, 56))

    def test_political_jog_is_absorbed_by_the_surrounding_country(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8, 8],
            [8, 1, 1, 1, 2, 2, 8],
            [8, 1, 1, 2, 2, 2, 8],
            [8, 1, 1, 1, 2, 2, 8],
            [8, 1, 1, 1, 2, 2, 8],
            [8, 8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON", 2: "NVR"})
        changed = builder.smooth_borders(state, (0, 0, 6, 5))
        self.assertGreater(changed, 0)
        jogs = 0
        for y in range(1, 5):
            for x in range(1, 6):
                index = y * 7 + x
                if not state.land[index]:
                    continue
                tag = state.owners[state.province_ids[index]]
                other = 0
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    neighbour = (y + dy) * 7 + (x + dx)
                    if state.land[neighbour] and state.owners[state.province_ids[neighbour]] != tag:
                        other += 1
                if other >= 3:
                    jogs += 1
        self.assertEqual(jogs, 0)

    def test_compact_country_blocks_keep_their_straight_border(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8],
            [8, 1, 1, 2, 2, 8],
            [8, 1, 1, 2, 2, 8],
            [8, 1, 1, 2, 2, 8],
            [8, 1, 1, 2, 2, 8],
            [8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON", 2: "NVR"})
        builder.smooth_borders(state, (0, 0, 5, 5))
        left = {state.province_ids[y * 6 + 1] for y in range(2, 4)}
        right = {state.province_ids[y * 6 + 3] for y in range(2, 4)}
        self.assertEqual(left, {1})
        self.assertEqual(right, {2})

    def test_one_pixel_coastal_spur_is_removed(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8],
            [8, 8, 1, 8, 8, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "NVR"})
        builder.smooth_borders(state, (0, 0, 5, 5))
        self.assertFalse(state.land[1 * 6 + 2])
        self.assertTrue(state.land[2 * 6 + 2])

    def test_wide_peninsula_is_kept(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8, 8],
            [8, 1, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 1, 8],
            [8, 8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "NVR"})
        builder.smooth_borders(state, (0, 0, 6, 6))
        self.assertTrue(state.land[3 * 7 + 2])
        self.assertTrue(state.land[3 * 7 + 3])
        self.assertTrue(state.land[3 * 7 + 4])

    def test_one_pixel_inlet_is_filled(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 1, 8, 1, 1, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 1, 1, 1, 1, 8],
            [8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON"})
        builder.smooth_borders(state, (0, 0, 5, 6))
        self.assertTrue(state.land[3 * 6 + 2])
        self.assertEqual(state.province_ids[3 * 6 + 2], 1)

    def test_assignment_refuses_to_empty_or_disconnect_a_province(self) -> None:
        grid = [
            [8, 8, 8, 8],
            [8, 1, 2, 8],
            [8, 8, 2, 8],
            [8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON", 2: "NVR"})
        self.assertFalse(builder.can_reassign(state, 1 * 4 + 1, 2))

    def test_definition_coastal_flags_follow_new_land_sea_edges(self) -> None:
        grid = [
            [8, 8, 8, 8, 8],
            [8, 1, 1, 1, 8],
            [8, 1, 1, 1, 8],
            [8, 1, 1, 1, 8],
            [8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON"})
        flags = builder.coastal_flags(state, {1, 8})
        self.assertTrue(flags[1])
        self.assertTrue(flags[8])
        payload = builder.render_definition(
            ["1;10;20;30;land;false;plains;1", "8;0;0;80;sea;false;ocean;0"],
            "\n",
            True,
            flags,
        )
        self.assertTrue(payload.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"1;10;20;30;land;true;plains;1", payload)

    def test_political_stair_step_is_rounded(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8, 8, 8],
            [8, 1, 1, 1, 1, 2, 2, 8],
            [8, 1, 1, 1, 2, 2, 2, 8],
            [8, 1, 1, 1, 2, 2, 2, 8],
            [8, 1, 1, 1, 2, 2, 2, 8],
            [8, 8, 8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON", 2: "NVR"})
        builder.smooth_borders(state, (0, 0, 7, 5))
        self.assertEqual(state.province_ids[1 * 8 + 4], state.province_ids[2 * 8 + 4])

    def test_second_smoothing_pass_is_idempotent(self) -> None:
        grid = [
            [8, 8, 8, 8, 8, 8],
            [8, 1, 1, 1, 2, 8],
            [8, 1, 1, 2, 2, 8],
            [8, 1, 1, 1, 2, 8],
            [8, 1, 1, 1, 2, 8],
            [8, 8, 8, 8, 8, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON", 2: "NVR"})
        builder.smooth_borders(state, (0, 0, 5, 5))
        snapshot = array("I", state.province_ids)
        self.assertEqual(builder.smooth_borders(state, (0, 0, 5, 5)), 0)
        self.assertEqual(list(state.province_ids), list(snapshot))

    def test_provinces_image_preserves_assigned_colours(self) -> None:
        grid = [
            [1, 1],
            [1, 8],
        ]
        state = _state_from_grid(grid, {8: "sea"}, {1: "HON"})
        image = builder.provinces_image(state)
        self.assertEqual(image.size, (2, 2))
        self.assertEqual(image.getpixel((1, 1)), (0, 0, 80))

    def test_load_owners_reads_state_history(self) -> None:
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "396-outer-right.txt"
            path.write_text(
                "state = {\n\tid = 396\n\thistory = { owner = HON }\n\tprovinces = { 11 12 }\n}\n",
                encoding="utf-8",
            )
            self.assertEqual(builder.load_owners(Path(temporary)), {11: "HON", 12: "HON"})


if __name__ == "__main__":
    unittest.main()
