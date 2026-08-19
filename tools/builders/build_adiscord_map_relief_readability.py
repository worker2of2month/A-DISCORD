#!/usr/bin/env python3
"""Rebuild map relief so every province looks like the terrain it declares.

A-DISCORD inherited a converted map whose gameplay terrain in
``map/definition.csv`` had drifted away from what the player actually sees.  A
numeric comparison against a reference generator found that the visible defects
all shared one root cause, and it was not the one the screenshots suggested.

``map/heightmap.bmp`` had been linearly stretched by 5/3 at some point in its
history and rounded back to integers.  Only 35 land elevations carried more than
five thousand pixels and they ascended 2, 2, 1 repeating, so 40% of the
available integers were empty.  A gentle slope was therefore *unrepresentable*:
68.5% of neighbouring land pixels sat on the same rung and rendered as dead-flat
plateau, while 18.9% jumped a whole rung at once.  The step histogram had a hole
at one unit and a spike at two, which no natural surface can produce.  The
"vertical walls" players saw were not unusually steep - our maximum step of 62
is comparable to the reference's 58 - they were simply the *only* gradient
present, so they read as walls against flat surroundings.

This builder therefore owns four outputs:

* ``map/heightmap.bmp`` - a global relief pass over every land pixel.  It
  de-quantises the inherited ladder, adds surface roughness at the pixel scale,
  and drives large-scale relief from each province's declared terrain through
  :data:`RELIEF_PROFILE`.  Amplitude spreads across province borders so ranges
  join into massifs instead of stopping at a polygon edge.
* ``map/world_normal.bmp`` - regenerated globally from the finished heightmap
  with the unnormalised Sobel encoding HOI4 actually expects (see
  :func:`tools.lib.map_relief.sobel_normal`).
* ``map/terrain.bmp`` - relief-aware dominant-terrain repaint for the frozen
  province scope, the river corridor carved out of urban footprints, and the
  northern transition band.  The band is not province-scoped because neither of
  its defects is: the inherited art carries a single-row index seam at
  ``y = 300`` crossing provinces nobody froze into a scope, and the warm
  ``mountain_variation_grass`` and ``desert_mountain`` textures reach the ice cap
  from everywhere.  See :data:`NORTHERN_SEAM_ROW` and
  :data:`COLD_PALETTE_SUBSTITUTION`.
* ``map/trees.bmp`` - a subtractive pass that pulls foliage back off the
  shoreline.

The repaint is deliberately *not* a province flood fill.  Every pixel is ranked
by a relief signal blended with domain-warped coherent noise, so each province
keeps a dominant readable terrain while its edges interleave organically with
its neighbours.  Snow stays owned by
:mod:`tools.builders.build_adiscord_terrain_snow`: every pixel this pass writes
is normalised through that builder's classifier, which makes the result a fixed
point of both generators regardless of apply order.

Relief lives here rather than in
:mod:`tools.builders.build_adiscord_province_layer_alignment` because a
per-province "raise the centre" pass cannot avoid pedestals at the province rim,
and its provinces are a subset of the land this pass already covers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO
from math import ceil
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
from PIL import Image

from tools.builders import build_adiscord_terrain_snow as snow
from tools.lib import map_relief as relief_math
from tools.lib.map_raster import (
    CATEGORY_PALETTE,
    PALETTE_TYPES,
    UNPAINTABLE_TERRAIN,
    URBAN_PALETTE,
    WATER_PALETTE,
    DefinitionRow,
    neighbours4,
    province_pixel_index,
    read_definition,
    river_corridor_indices,
    save_bitmap_atomically,
    warped_fbm,
)


ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = ROOT / "tools" / "data" / "adiscord_map_readability_scope.json"
# The pre-relief heightmap.  Sculpting reads its large-scale shape from here and
# never from ``map/heightmap.bmp``, because the sculpted relief is additive: using
# the output as the next run's input makes every run pile more relief onto the
# last and the builder stops being idempotent.  Stored as lossless PNG purely to
# keep the committed asset near one megabyte instead of eleven.
RELIEF_BASE_PATH = ROOT / "tools" / "data" / "adiscord_relief_base_heightmap.png"
# The pre-setback canopy, for the same reason.  Clearing trees is subtractive, so
# reading back the layer this pass wrote makes the setback a ratchet: widening it
# works, narrowing it silently does nothing because the cleared cells are already
# gone and there is nothing left to restore them from.
TREE_BASE_PATH = ROOT / "tools" / "data" / "adiscord_relief_base_trees.png"
PROVINCES_PATH = ROOT / "map" / "provinces.bmp"
DEFINITION_PATH = ROOT / "map" / "definition.csv"
TERRAIN_PATH = ROOT / "map" / "terrain.bmp"
HEIGHTMAP_PATH = ROOT / "map" / "heightmap.bmp"
WORLD_NORMAL_PATH = ROOT / "map" / "world_normal.bmp"
RIVERS_PATH = ROOT / "map" / "rivers.bmp"
TREES_PATH = ROOT / "map" / "trees.bmp"

# --- the sea-level contract -------------------------------------------------
# Vanilla HOI4 treats heights below 95 as water and this map has no
# ``map/default.map`` to override that.  Every water pixel is stored as exactly
# 89 and the lowest land pixel is 97; both are asserted before anything is
# written, so a relief pass can never move the coastline by a single pixel.
WATER_HEIGHT = relief_math.WATER_HEIGHT
SEA_LEVEL = relief_math.SEA_LEVEL
MIN_LAND_HEIGHT = relief_math.MIN_LAND_HEIGHT
MAX_RELIEF_HEIGHT = 250

# --- relief -----------------------------------------------------------------
# Per declared terrain: the amplitude in height units of each noise band, and
# the steepest single-pixel step the province may carry.
#
# Measured slope comes almost entirely from the *short*-wavelength bands.  This
# is the counter-intuitive part: a band with cell 44 and amplitude 34 adds a lot
# of height but almost no per-pixel gradient, because it changes by 34 units over
# 44 pixels.  So ``mid``/``coarse``/``ridge`` give a range its mass while
# ``fine`` and ``rough`` decide whether it reads as steep.
#
# The split between those two matters as much as their size.  ``fine`` is
# isotropic noise at the pixel scale and is pure surface texture; pushing enough
# of it into a mountain to reach the target slope turned whole ranges into
# uniform sandpaper that no longer showed a ridge line anywhere.  ``rough`` is
# *ridged and anisotropic* at cells 9 and 20, so it delivers the same gradient as
# lineaments - spurs, gullies and crests aligned to the range - instead of grain.
# Steep classes therefore take a modest ``fine`` and a large ``rough``.
#
# No terrain gets a zero in ``fine``: every real surface is rough at the pixel
# scale, and starving that band is what left most of this map sitting on the
# inherited height ladder.
#
# ``step`` is calibrated against the reference generator's measured per-class
# gradient (plains about 1, hills about 5, mountains about 10 units per pixel,
# steep peaks about 21), with a hard ceiling at :data:`MAX_ANY_STEP`.
#
# The amplitudes themselves are not guesses.  Each band was measured for the
# 95th-percentile gradient it delivers per unit of amplitude - ``fine`` 1.20,
# ``rough`` 0.73, ``mid`` 0.10, ``coarse`` and ``ridge`` 0.05 - so the value here
# is solved from the class's inherited slope and its reference target rather than
# found by trial.  That is also why the large-scale bands can carry ten to
# fourteen units without making anything steep: they are mass, not gradient.
#
# Mountain deliberately takes the *smallest* large-scale amplitudes of the steep
# classes.  Mountain provinces here already average 152 against a land mean of
# 116, so they were never too low - they were too smooth, and their remaining
# headroom under :data:`PEAK_SNOW_HEIGHT` is only about fifty units.  Spending
# that headroom on mass instead of texture just pinned them against the ceiling
# and flattened the tops, which is the opposite of the goal.
RELIEF_PROFILE: Mapping[str, tuple[float, float, float, float, float, int]] = {
    # terrain          fine  rough   mid  coarse  ridge  step
    "plains":         (0.70,  0.70,  1.8,   2.6,   0.0,   12),
    "forest":         (0.78,  1.00,  2.4,   3.6,   0.0,   12),
    "desert":         (0.75,  0.95,  2.2,   4.2,   0.0,   12),
    "marsh":          (0.48,  0.28,  0.7,   1.0,   0.0,    8),
    "urban":          (0.60,  0.45,  1.1,   1.6,   0.0,   10),
    "hills":          (1.50,  5.50,  6.0,  10.0,   8.0,   16),
    "mountain":       (2.20, 12.00,  8.0,  10.0,  14.0,   20),
    "contaminated":   (0.78,  1.00,  2.4,   3.6,   0.0,   12),
    "vorkernsberg":   (1.50,  5.50,  6.0,  10.0,   8.0,   18),
    "unknown":        (0.70,  0.70,  1.8,   2.6,   0.0,   12),
}
DEFAULT_PROFILE = RELIEF_PROFILE["plains"]
PROFILE_KEYS = ("fine", "rough", "mid", "coarse", "ridge", "step")
MAX_ANY_STEP = 24
MAX_ISLAND_STEP = 20
GRADIENT_SWEEPS = 16

# Permanent snow is owned by :mod:`tools.builders.build_adiscord_terrain_snow`,
# which caps a peak as permanently white at this height and validates the total
# snow pixel count.  Holding pixels on their own side of the threshold keeps that
# mask exactly invariant, so relief can be retuned without moving the snow line.
PEAK_SNOW_HEIGHT = snow.PERMANENT_PEAK_HEIGHT

# The de-quantisation contract, measured as 4-neighbour absolute height steps
# between land pixels.  The inherited map sat at 0.685 identical / 0.291 gentle
# with 133 populated elevations, which is the signature of a rounded 5/3 stretch
# rather than of any real surface.  The reference generator sits near 0.38 and
# 0.51.  These are ceilings and floors, not targets, so tuning relief upwards
# cannot silently break them.
MAX_FLAT_SHARE = 0.45
MIN_GENTLE_SHARE = 0.45
MIN_POPULATED_HEIGHTS = 150

# The reference generator's measured 95th-percentile slope per terrain class, in
# height units per pixel.  These are the numbers that decide whether a province
# *reads* as its declared terrain, and :data:`MIN_CLASS_SLOPE` holds the classes
# a player is most likely to misread to a fraction of them.
REFERENCE_CLASS_SLOPE: Mapping[str, float] = {
    "plains": 1.03,
    "forest": 1.43,
    "desert": 1.43,
    "hills": 4.76,
    "mountain": 10.07,
}
MIN_CLASS_SLOPE: Mapping[str, float] = {"hills": 2.6, "mountain": 5.0}

# Surface roughness: a band-limited stack from the pixel scale up.  These
# amplitudes were calibrated against the reference generator's neighbour-step
# distribution; see ``docs/map/relief-readability-2026-08-19.md``.
FINE_BANDS: tuple[tuple[int, float], ...] = ((2, 0.9), (4, 1.8), (8, 2.8))
# Ridged bands that carry slope as lineaments rather than as grain.  Three
# wavelengths, weighted towards the longest: the 9 px band supplies the gradient,
# while 20 and 38 px organise it into spurs and gullies of more than one size so
# the range does not read as corduroy of a single scale.
ROUGH_BANDS: tuple[tuple[int, float], ...] = ((9, 1.0), (20, 1.15), (38, 1.3))
ROUGH_MEAN = 0.42                 # approximate mean of the ridged field
# Roughness is gated by a slow coherent field, so a range breaks into rough faces
# separated by smoother basins and shoulders rather than being uniformly broken.
# The floor is deliberately low: without near-smooth patches there is nothing for
# the rough ground to contrast against.
ROUGH_GATE_CELL = 110
ROUGH_GATE_FLOOR = 0.2
MID_CELL = 20
COARSE_CELL = 44
RIDGE_CELL = 58
RIDGE_TREND_DEGREES = 24          # tectonic strike of the ranges
RIDGE_ACROSS_SCALE = 0.58         # <1 stretches crests along the strike
RIDGE_SHARPNESS = 1.9
RIDGE_FLOOR = 0.45                # crest value that counts as "no ridge"
NOISE_SALT_FINE = 6197
NOISE_SALT_MID = 8821
NOISE_SALT_COARSE = 9173
NOISE_SALT_RIDGE = 6101
NOISE_SALT_ROUGH = 7433
NOISE_SALT_ROUGH_GATE = 4519

AMPLITUDE_SPREAD_STEPS = 8        # how far a range's foothills reach outward
AMPLITUDE_SPREAD_DECAY = 0.09
AMPLITUDE_BLUR_PASSES = 2
BASE_BLUR_PASSES = 1              # de-terraces the inherited ladder

# --- coastline --------------------------------------------------------------
# The reference generator keeps its first land pixel about 1.6 units above sea
# level and accelerates outwards; ours started 6.9 units up and gained another
# 2.2 in a single pixel, which is a beach cliff.
#
# These ceilings trace the reference generator's *95th percentile* by distance
# from water, not its mean, and are measured from :data:`MIN_LAND_HEIGHT`.  That
# distinction matters more than it looks: its mean coastal height stays near 103
# out to twenty pixels, but its p95 is already 142 there, because plenty of real
# coast is mountainous.  Capping to the mean flattened every coastal massif on a
# map that is one third land and full of islands - including the whole northern
# island, which is nowhere more than a few dozen pixels from water.
#
# Past the measured band the ceiling is released over a smoothstep rather than at
# once.  A step here is not harmless: the table used to end at 47 and the next
# pixel jumped to the full 153, which printed a hard-edged ring of suppressed
# relief right around every coast - a visible bare belt with a straight inland
# edge exactly where the table ran out.
COAST_CEILING: tuple[int, ...] = (
    0, 2, 4, 6, 8, 11, 14, 16, 18, 21, 23, 25, 28, 30, 33, 35, 38, 40, 43, 45, 47,
)
COAST_MOUNTAIN_BAND = 11          # mountain amplitude ramps in over this band
COAST_DISTANCE_LIMIT = 64
COAST_RELEASE_DISTANCE = 64       # where the ceiling reaches its inland value

# --- island -----------------------------------------------------------------
# The northern island ("Reydal") was a dead-flat platform carrying one terraced
# cone, so its baseline carries no usable structure and is rebuilt outright.
ISLAND_SHORE_HEIGHT = 99
ISLAND_BASE_GAIN = 22
ISLAND_COAST_BAND = 9             # pixels over which the shore climbs inland

# --- rivers -----------------------------------------------------------------
# A channel must lie on a valley floor, not along the crest of an embankment.
# ``INTAKE`` pulls the channel itself down to what its close surroundings justify,
# and ``VALLEY``/``BANK_SLOPE`` then cap the banks so they descend to the water
# over about a dozen pixels.  The bank slope is deliberately below the mountain
# step cap, so a river crossing a range carves a gorge with graded walls instead
# of a one-pixel slot.
RIVER_INTAKE_BAND = 3
RIVER_INTAKE_SLOPE = 1.0
RIVER_VALLEY_BAND = 12
RIVER_BANK_SLOPE = 1.9

# --- level pads -------------------------------------------------------------
# HOI4's building models are rigid, so they sink into or protrude from sloped
# ground.  Every province whose declared terrain is urban is therefore levelled,
# along with the Tower of Unity's province, whose single tall landmark exposes a
# grade more than a block of houses does.
#
# Each province is levelled to *its own* median rather than to a shared height.
# That keeps the mean elevation where it was, and it means a city spread across
# several provinces on a hillside becomes a flight of level terraces - which is
# what a real hillside city looks like - instead of one implausible plane.  The
# ramp band is what keeps a terrace from becoming a plinth: the surrounding relief
# climbs to meet it over sixteen pixels, well inside the plains step cap.
PAD_TERRAIN = ("urban",)
PAD_PROVINCE_IDS: frozenset[int] = frozenset({16428})
PAD_BLEND_BAND = 16
MAX_PAD_SPREAD = 0.0              # each levelled province must be exactly level
# The slope a levelled province may still carry once the ramp and the gradient cap
# have run, in height units per pixel.  The reference generator puts plains at
# about 1.03, and a city has to be at least that flat for a rigid model to sit on
# it convincingly.
MAX_URBAN_SLOPE = 1.2

# --- world normal -----------------------------------------------------------
# ``world_normal.bmp`` is *not* a unit-length tangent-space normal.  Matching the
# reference generator's own Sobel dump reproduces it exactly with the raw 3x3
# OpenCV kernels at full heightmap resolution, no division by eight, blue pinned,
# and no normalisation; vanilla's neutral flat normal is the constant
# ``(128, 128, 255)``.  The previous encoding used a 127 centre, blue 253 and an
# effective gain of 3.3 taken from 2x2-averaged heights, which threw away every
# single-pixel detail before the gradient was computed and cost roughly 2.4x of
# the available relief contrast.
NORMAL_SOBEL_FACTOR = 1.0
NORMAL_CENTER = 128
NORMAL_BLUE = 255

# --- trees ------------------------------------------------------------------
# ``trees.bmp`` is 1650x600, so one tree cell covers 3.41 x 3.41 full-resolution
# pixels.  Taking the majority terrain across that footprint let a cell that was
# 49% ocean still render foliage, which is why trees stood in the surf.
# Rejecting wet cells already pulls the canopy roughly one cell inland, because a
# cell only has to touch water to be rejected.  A further uniform setback on top
# of that produced a bare belt of constant width tracing the whole coast, which
# reads as an artificial exclusion ring - worse than a treeline standing slightly
# too close to the surf.  So the extra cell is applied to only part of the shore,
# chosen by coherent noise, which leaves a ragged edge with tongues and pockets
# and no continuous outline anywhere.
TREE_NONE_INDEX = 0               # the palette entry meaning "no trees here"
TREE_WATER_TOLERANCE = 0.0        # any water in the footprint rejects the cell
TREE_COAST_SETBACK = 1            # tree cells the canopy must hold back inland
TREE_RAGGED_CELL = 7              # patch size of the irregular extra setback
TREE_RAGGED_THRESHOLD = 0.15      # noise level above which that cell is cleared
NOISE_SALT_TREE_EDGE = 3571

# --- terrain repaint --------------------------------------------------------
# The dominant share each declared terrain must reach inside its province.
# Mountain is deliberately the highest: a mountain province has to read as
# mountains across essentially its whole area.
DOMINANT_SHARE: Mapping[str, float] = {
    "mountain": 0.86,
    "hills": 0.76,
    "forest": 0.76,
    "plains": 0.74,
    "desert": 0.80,
    "marsh": 0.78,
    "urban": 1.00,
}
# Urban provinces lose area to the river corridor on purpose, so they are held
# to a readable-city floor instead of the full-coverage target.
MINIMUM_SHARE: Mapping[str, float] = {
    "mountain": 0.84,
    "hills": 0.72,
    "forest": 0.72,
    "plains": 0.70,
    "desert": 0.76,
    "marsh": 0.74,
    "urban": 0.55,
}
URBAN_CORRIDOR_FLOOR = 0.62
TERRAIN_NOISE_CELL = 11
TERRAIN_NOISE_WEIGHT = 0.34
VARIANT_NOISE_CELL = 7
# Rank thresholds that split a mountain province into grass benches, rock faces
# and bare peaks.  Both must stay below 1.0 or a province would resolve flat.
MOUNTAIN_ROCK_RANK = 0.34
MOUNTAIN_PEAK_RANK = 0.68
RIVER_CORRIDOR_RADIUS = 1
CORRIDOR_BANK_CATEGORY = "plains"

# --- the northern index seam -------------------------------------------------
# The converted base art carries a single-row terrain-index seam at exactly this
# row and nowhere else: 656 of the 2111 land pixels in the row change index in
# one step against 7-12% in every neighbouring row, and the change is dominated
# by 343 columns switching plains to ``hills_blend`` with unbroken runs of 89 and
# 48 pixels.  That is the straight line visible across the northern continent.
# No generator authored it - it predates every pass in this repository - so it is
# dissolved here, because the province repaint above only covers its frozen
# scope and the seam crosses provinces that are not in it.
#
# The dissolve reads the two indices the band's *outside* anchor rows carry and
# redistributes the boundary between them over a band whose depth varies along x.
# Reading the anchors from rows this pass never writes is what makes it a fixed
# point: a second run derives the same pair, the same per-column depth and the
# same per-pixel choice, so nothing moves.  Only pixels that already carry one of
# the two anchor indices are eligible, so the local variety inside the band -
# marsh pockets, rock outcrops, 7.6% of its area - survives untouched.
NORTHERN_SEAM_ROW = 300
NORTHERN_SEAM_DEPTH = 6           # widest half-band, and the anchor offset
NORTHERN_SEAM_MIN_SCALE = 0.45    # narrowest local band as a share of the above
NORTHERN_SEAM_WIDTH_CELL = 150    # how slowly the band depth varies along x
NORTHERN_SEAM_EDGE_CELL = 34      # how slowly the boundary row itself wanders
NORTHERN_SEAM_EDGE_SHAPE = 0.62   # <1 pushes the edge out towards the band limits
NORTHERN_SEAM_DETAIL_CELL = 10    # size of the interlocking tongues and pockets
# The pocket term is scaled by the local band depth, so a pocket can carry one
# terrain a couple of rows across the edge; that is what makes the two
# interdigitate rather than merely follow a wavy line.
NORTHERN_SEAM_NOISE_WEIGHT = 0.5
NOISE_SALT_SEAM_WIDTH = 5281
NOISE_SALT_SEAM_EDGE = 7717
NOISE_SALT_SEAM_DETAIL = 8663

# --- northern palette temperature -------------------------------------------
# ``mountain_variation_grass`` (palette 20) is a green pasture texture and it is
# the *first* entry of ``CATEGORY_PALETTE["mountain"]``, so every mountain pixel
# that is not steep enough to score as rock is painted lush green - including
# 11,526 pixels within 160 px of the ice cap, 9,310 of them inside provinces that
# ``definition.csv`` declares plains.  ``desert_mountain`` (palette 2) is a sandy
# hills texture and puts 18,132 more warm pixels in the same band.  Next to white
# snow and grey rock both read as absurd.
#
# Every substitution is category-preserving on purpose: 20, 18 and 27 are all
# ``mountain`` in ``common/terrain/00_terrain.txt`` and so is 11, while 2 and 17
# are both ``hills``.  Only the *texture* changes, so no province's declared
# terrain readability share moves by a single pixel and no gameplay terrain is
# touched.  ``00_terrain.txt`` defines no boreal forest entry - both forest
# indices, 1 and 4, sit on textures 4 and 5 which jungle also uses - so forest is
# deliberately left alone rather than recoloured into a category it is not.
COLD_PALETTE_SUBSTITUTION: Mapping[int, int] = {
    2: 17,     # desert_mountain, texture 3       -> hills_blend, texture 2
    18: 11,    # mountain_variation_sand, tex 7   -> rocky mountain, texture 11
    20: 11,    # mountain_variation_grass, tex 7  -> rocky mountain, texture 11
    27: 11,    # mountain on texture 7            -> rocky mountain, texture 11
}
# How far south of the permanent-snow edge the substitution reaches, and the
# noise that breaks its own boundary.  A hard cutoff here would simply trade one
# straight line for another, so the swap is certain against the ice cap, even
# odds two thirds of the way down and absent at the far edge.
COLD_BAND_DEPTH = 200
COLD_BAND_BIAS = 0.35
COLD_BAND_NOISE_CELL = 26
COLD_BAND_NOISE_WEIGHT = 0.35
NOISE_SALT_COLD_BAND = 6421


@dataclass
class ReliefStats:
    height_changed: int = 0
    gradient_moved: int = 0
    island_step: int = 0
    descent_moved: int = 0
    descent_climb: float = 0.0
    pad_spread: float = 0.0
    pad_provinces: int = 0
    pad_slope_before: float = 0.0
    pad_slope_after: float = 0.0
    step_before: dict[str, float] = field(default_factory=dict)
    step_after: dict[str, float] = field(default_factory=dict)
    class_slope_before: dict[str, float] = field(default_factory=dict)
    class_slope_after: dict[str, float] = field(default_factory=dict)


@dataclass
class TerrainStats:
    changed: set[int] = field(default_factory=set)
    declared: dict[int, str] = field(default_factory=dict)
    share_before: dict[int, float] = field(default_factory=dict)
    share_after: dict[int, float] = field(default_factory=dict)
    slope_after: dict[int, float] = field(default_factory=dict)
    corridor_cleared: int = 0
    corridor_provinces: set[int] = field(default_factory=set)
    seam_interleaved: int = 0
    seam_share_before: float = 0.0
    seam_share_after: float = 0.0
    cold_substituted: Counter[int] = field(default_factory=Counter)


@dataclass
class BuildOutputs:
    heightmap: Image.Image
    world_normal: Image.Image
    terrain: Image.Image
    trees: Image.Image
    relief: ReliefStats
    terrain_stats: TerrainStats
    normal_changed: int
    trees_cleared: int
    # The cells of ``map/terrain.bmp`` and ``map/trees.bmp`` this builder actually
    # claims.  Comparing the whole of either file instead reported 30 terrain
    # bytes and 7 tree cells that
    # :mod:`tools.builders.build_adiscord_province_layer_alignment` legitimately
    # owns and writes afterwards, so ``--check`` could not be trusted.
    terrain_claim: np.ndarray | None = None
    tree_claim: np.ndarray | None = None


def load_relief_base(heightmap: Image.Image) -> np.ndarray:
    """Return the pre-relief heights this pass sculpts from.

    Sculpting is additive, so it must never read the heightmap it just wrote or a
    second run would stack a second copy of the relief on top of the first.  The
    baseline is therefore a committed asset, seeded once with ``--seed-base``.
    """

    if not RELIEF_BASE_PATH.exists():
        raise RuntimeError(
            f"{RELIEF_BASE_PATH.relative_to(ROOT).as_posix()} is missing; seed it "
            "from an unsculpted map/heightmap.bmp with --seed-base"
        )
    with Image.open(BytesIO(RELIEF_BASE_PATH.read_bytes())) as image:
        if image.mode != "L":
            raise RuntimeError(
                f"the relief baseline must stay 8-bit greyscale, found {image.mode}"
            )
        base = np.asarray(image, dtype=np.uint8).copy()
    if base.shape != (heightmap.size[1], heightmap.size[0]):
        raise RuntimeError("relief baseline dimensions differ from map/heightmap.bmp")
    return base


def load_tree_base(trees: Image.Image) -> np.ndarray:
    """Return the pre-setback canopy this pass subtracts from.

    The baseline is read as raw palette indices.  ``trees.bmp`` stores a tree
    *type* per index, so converting it to greyscale anywhere in this path is
    corruption rather than a format detail: it silently replaces every index with
    the luminance of its palette colour, turning tree type 6 into the grey entry
    87 and planting whatever model that index happens to name.
    """

    if not TREE_BASE_PATH.exists():
        raise RuntimeError(
            f"{TREE_BASE_PATH.relative_to(ROOT).as_posix()} is missing; seed it "
            "from an unmodified map/trees.bmp with --seed-base"
        )
    with Image.open(BytesIO(TREE_BASE_PATH.read_bytes())) as image:
        if image.mode != "P":
            raise RuntimeError(
                "the tree baseline must stay paletted so its indices survive; "
                f"found mode {image.mode}"
            )
        base = np.asarray(image, dtype=np.uint8).copy()
    if base.shape != (trees.size[1], trees.size[0]):
        raise RuntimeError("tree baseline dimensions differ from map/trees.bmp")
    return base


def seed_relief_base() -> list[str]:
    """Capture the current rasters as the baselines this pass sculpts from.

    The images are stored in their own mode, never converted.  A paletted raster
    converted to greyscale loses its indices, and for ``trees.bmp`` those indices
    are the tree types.

    Existing baselines are never overwritten: the rasters on disk are normally the
    *sculpted* ones, so re-seeding would bake this pass's own output into its input
    and reintroduce the accumulation the baselines exist to prevent.
    """

    written: list[str] = []
    for source, target in ((HEIGHTMAP_PATH, RELIEF_BASE_PATH), (TREES_PATH, TREE_BASE_PATH)):
        if target.exists():
            continue
        with Image.open(BytesIO(source.read_bytes())) as image:
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, format="PNG", optimize=True)
        written.append(target.relative_to(ROOT).as_posix())
    return written


def load_scope(path: Path = SCOPE_PATH) -> dict[str, frozenset[int]]:
    """Load and validate the frozen province scope."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise RuntimeError("readability scope schema must be 1")
    keys = (
        "northern_island_provinces",
        "flat_mountain_provinces",
        "terrain_mismatch_provinces",
        "urban_river_provinces",
    )
    scope: dict[str, frozenset[int]] = {}
    for key in keys:
        values = payload.get(key)
        if not isinstance(values, list) or not values:
            raise RuntimeError(f"readability scope: {key} must be a non-empty list")
        if any(not isinstance(value, int) or value <= 0 for value in values):
            raise RuntimeError(f"readability scope: {key} must hold province ids")
        if len(set(values)) != len(values):
            raise RuntimeError(f"readability scope: {key} repeats a province id")
        scope[key] = frozenset(values)
    island = scope["northern_island_provinces"]
    for key in ("flat_mountain_provinces", "terrain_mismatch_provinces"):
        if island & scope[key]:
            raise RuntimeError(f"readability scope: {key} overlaps the island scope")
    if scope["flat_mountain_provinces"] & scope["terrain_mismatch_provinces"]:
        raise RuntimeError("readability scope: flat-mountain and mismatch scopes overlap")
    return scope


def relief_province_ids(scope: Mapping[str, frozenset[int]]) -> frozenset[int]:
    return scope["northern_island_provinces"] | scope["flat_mountain_provinces"]


def terrain_province_ids(scope: Mapping[str, frozenset[int]]) -> frozenset[int]:
    return (
        scope["northern_island_provinces"]
        | scope["flat_mountain_provinces"]
        | scope["terrain_mismatch_provinces"]
        | scope["urban_river_provinces"]
    )


def _smoothstep(value: float) -> float:
    clamped = max(0.0, min(1.0, value))
    return clamped * clamped * (3.0 - 2.0 * clamped)


def terrain_code_field(
    provinces: Image.Image, definition: Mapping[int, DefinitionRow]
) -> tuple[np.ndarray, np.ndarray, tuple[str, ...]]:
    """Return ``(codes, land, category_names)`` for every map pixel.

    ``codes`` indexes ``category_names``; water pixels carry ``-1``.  A province
    colour that is not in ``definition.csv`` is treated as water so an unmapped
    pixel can never be handed relief.
    """

    array = np.asarray(provinces.convert("RGB"), dtype=np.uint8)
    packed = relief_math.packed_colours(array)
    names = tuple(sorted({row.terrain for row in definition.values() if row.is_land}))
    code_of = {name: index for index, name in enumerate(names)}
    colours: list[int] = []
    codes: list[int] = []
    for row in definition.values():
        red, green, blue = row.color
        colours.append((red << 16) | (green << 8) | blue)
        codes.append(code_of[row.terrain] if row.is_land else -1)
    field_codes = relief_math.map_colours_to_codes(packed, colours, codes, -1)
    return field_codes, field_codes >= 0, names


def profile_fields(
    codes: np.ndarray, land: np.ndarray, names: Sequence[str]
) -> dict[str, np.ndarray]:
    """Return the per-pixel amplitude and step-cap fields.

    Each field is grown outwards with :func:`map_relief.spread_maximum` and then
    blurred, so a range's foothills reach into the neighbouring provinces and no
    amplitude change lands exactly on a province polygon edge - a discontinuity
    there would draw the province outline into the relief itself.
    """

    lookup = np.zeros((len(names), len(PROFILE_KEYS)), dtype=np.float32)
    for index, name in enumerate(names):
        lookup[index] = RELIEF_PROFILE.get(name, DEFAULT_PROFILE)
    safe = np.where(land, codes, 0).astype(np.intp)
    fields: dict[str, np.ndarray] = {}
    for column, key in enumerate(PROFILE_KEYS):
        raw = np.where(land, lookup[safe, column], np.float32(0.0)).astype(np.float32)
        spread = relief_math.spread_maximum(
            raw, land, AMPLITUDE_SPREAD_STEPS, AMPLITUDE_SPREAD_DECAY * float(raw.max())
        )
        fields[key] = relief_math.masked_blur(spread, land, AMPLITUDE_BLUR_PASSES)
    return fields


def relief_bands(shape: tuple[int, int], land: np.ndarray) -> dict[str, np.ndarray]:
    """Evaluate the shared noise bands once for the whole map."""

    fine = np.zeros(shape, dtype=np.float32)
    for order, (cell, units) in enumerate(FINE_BANDS):
        fine += relief_math.striped_field(
            shape,
            lambda xs, ys, c=cell, s=NOISE_SALT_FINE + order * 1301: relief_math.value_noise(
                xs, ys, c, s
            ),
        ) * np.float32(units)
    # Ridged at three short wavelengths and rotated onto the same strike as the
    # massif crests, so the gradient it contributes arrives as spurs and gullies
    # that follow the range rather than as isotropic grain.
    #
    # Each band is standardised to zero mean and unit deviation before weighting.
    # Ridging is a strongly non-linear transform - ``(1-|fbm|)**1.9`` collapses
    # towards its own mean - so the raw field only deviates by about 0.1, and an
    # amplitude of "16 units" was in truth delivering under two.  Standardising
    # makes the numbers in :data:`RELIEF_PROFILE` mean height units again.
    rough = np.zeros(shape, dtype=np.float32)
    for order, (cell, units) in enumerate(ROUGH_BANDS):
        band = relief_math.striped_field(
            shape,
            lambda xs, ys, c=cell, s=NOISE_SALT_ROUGH + order * 977: relief_math.ridged(
                xs,
                ys,
                c,
                s,
                RIDGE_TREND_DEGREES,
                RIDGE_ACROSS_SCALE,
                RIDGE_SHARPNESS,
                octaves=2,
            ),
        )
        sample = band[land] if land.any() else band
        spread = float(sample.std())
        band = (band - np.float32(float(sample.mean()))) / np.float32(max(spread, 1e-6))
        rough += band * np.float32(units)
    gate = relief_math.striped_field(
        shape,
        lambda xs, ys: relief_math.value_noise(
            xs, ys, ROUGH_GATE_CELL, NOISE_SALT_ROUGH_GATE
        ),
    )
    rough *= np.float32(ROUGH_GATE_FLOOR) + np.float32(1.0 - ROUGH_GATE_FLOOR) * np.clip(
        gate * np.float32(0.5) + np.float32(0.5), 0.0, 1.0
    )
    mid = relief_math.striped_field(
        shape,
        lambda xs, ys: relief_math.warped_fbm(xs, ys, MID_CELL, NOISE_SALT_MID, octaves=2),
    )
    coarse = relief_math.striped_field(
        shape,
        lambda xs, ys: relief_math.warped_fbm(
            xs, ys, COARSE_CELL, NOISE_SALT_COARSE, octaves=3
        ),
    )
    crest = relief_math.striped_field(
        shape,
        lambda xs, ys: relief_math.ridged(
            xs,
            ys,
            RIDGE_CELL,
            NOISE_SALT_RIDGE,
            RIDGE_TREND_DEGREES,
            RIDGE_ACROSS_SCALE,
            RIDGE_SHARPNESS,
            octaves=3,
        ),
    )
    return {"fine": fine, "rough": rough, "mid": mid, "coarse": coarse, "crest": crest}


def coastal_ceiling(distance: np.ndarray) -> np.ndarray:
    """Return the height ceiling each land pixel may reach near the shore."""

    table = np.array(COAST_CEILING, dtype=np.float32)
    edge = len(COAST_CEILING) - 1
    inland = np.float32(MAX_RELIEF_HEIGHT - MIN_LAND_HEIGHT)
    measured = table[np.clip(distance, 0, edge)]
    span = np.float32(max(COAST_RELEASE_DISTANCE - edge, 1))
    release = np.clip((distance.astype(np.float32) - np.float32(edge)) / span, 0.0, 1.0)
    release = release * release * (np.float32(3.0) - np.float32(2.0) * release)
    return table[edge] + (inland - table[edge]) * release + np.where(
        distance <= edge, measured - table[edge], np.float32(0.0)
    )


def build_global_relief(
    heights: np.ndarray,
    land: np.ndarray,
    codes: np.ndarray,
    names: Sequence[str],
    island: np.ndarray,
    channel: np.ndarray,
    pad_labels: np.ndarray,
) -> tuple[np.ndarray, ReliefStats]:
    """Rebuild relief over every land pixel.  Water is never touched."""

    stats = ReliefStats()
    original = heights.copy()
    stats.step_before = _step_summary(original, land)

    fields = profile_fields(codes, land, names)
    bands = relief_bands(heights.shape, land)
    coast = relief_math.edge_distance(land, COAST_DISTANCE_LIMIT)
    # A mountain range that runs straight into the surf reads as a quarry face,
    # so large-scale amplitude fades out over the last few pixels of shore.
    shore_ramp = np.clip(
        coast.astype(np.float32) / np.float32(COAST_MOUNTAIN_BAND), 0.0, 1.0
    )
    shore_ramp = shore_ramp * shore_ramp * (np.float32(3.0) - np.float32(2.0) * shore_ramp)

    base = relief_math.masked_blur(heights.astype(np.float32), land, BASE_BLUR_PASSES)
    if island.any():
        # The island's baseline is a flat platform, so it carries no structure
        # worth preserving and its base is rebuilt as a shore-to-inland ramp.
        depth = relief_math.edge_distance(island, ISLAND_COAST_BAND * 3)
        inland = np.clip(depth.astype(np.float32) / np.float32(ISLAND_COAST_BAND), 0.0, 1.0)
        inland = inland * inland * (np.float32(3.0) - np.float32(2.0) * inland)
        base = np.where(
            island,
            np.float32(ISLAND_SHORE_HEIGHT) + np.float32(ISLAND_BASE_GAIN) * inland,
            base,
        )

    field = (
        base
        + bands["fine"] * fields["fine"]
        + bands["rough"]
        * fields["rough"]
        * (np.float32(0.35) + np.float32(0.65) * shore_ramp)
        + bands["mid"] * fields["mid"] * shore_ramp
        + bands["coarse"] * fields["coarse"] * shore_ramp
        + np.maximum(bands["crest"] - np.float32(RIDGE_FLOOR), np.float32(0.0))
        / np.float32(1.0 - RIDGE_FLOOR)
        * fields["ridge"]
        * shore_ramp
    )
    ceiling = np.float32(MIN_LAND_HEIGHT) + coastal_ceiling(coast)
    field = np.minimum(field, np.maximum(ceiling, base))
    field = np.minimum(field, _peak_ceiling(original, land))
    field = np.clip(field, MIN_LAND_HEIGHT, MAX_RELIEF_HEIGHT)

    # Rivers, in three stages.  First the channel itself is driven down to the
    # lowest height its immediate surroundings justify, then descent to the sea is
    # enforced along it, then the banks are capped so they slope *down* to the
    # water.  Doing it in that order matters: capping the banks against a channel
    # that still climbs would carve the valley into the wrong shape.
    if channel.any():
        channel_land = channel & land
        field = np.where(
            channel_land,
            np.minimum(field, relief_math.corridor_allowance(
                field, channel_land, RIVER_INTAKE_BAND, RIVER_INTAKE_SLOPE
            )),
            field,
        )
        outlet = np.zeros(land.shape, dtype=bool)
        wet = ~land
        for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
            outlet |= np.roll(wet, shift, axis=axis)
        field, stats.descent_moved, stats.descent_climb = relief_math.enforce_descent(
            field, channel_land, outlet | (channel_land & (field <= MIN_LAND_HEIGHT))
        )
        valley = relief_math.corridor_allowance(
            field, channel_land, RIVER_VALLEY_BAND, RIVER_BANK_SLOPE
        )
        field = np.where(land, np.minimum(field, valley), field)
        field = np.clip(field, MIN_LAND_HEIGHT, MAX_RELIEF_HEIGHT)

    # The level pads run after every noise band and after the river valleys,
    # because anything that ran later would put the roughness straight back and
    # leave the models standing on a rippled floor.  That ordering is also what
    # exempts them from the de-quantisation detail.
    pad = (pad_labels > 0) & land
    if pad.any():
        labels = np.where(land, pad_labels, 0)
        field = relief_math.level_pads(field, labels, land, PAD_BLEND_BAND)
        stats.pad_spread = _pad_spread(field, labels)

    # The gradient cap runs last so nothing downstream can reintroduce a wall.
    step_cap = np.maximum(fields["step"], np.float32(1.0))
    stats.gradient_moved = relief_math.limit_gradient(
        field, land, np.minimum(step_cap, np.float32(MAX_ANY_STEP)), GRADIENT_SWEEPS
    )
    # The cap can nudge a channel pixel back up, so descent is re-established and
    # the pad re-levelled afterwards.  Both only ever lower ground, so neither can
    # undo the cap by creating a new step above it.
    if channel.any():
        field, moved, climb = relief_math.enforce_descent(
            field, channel & land, outlet | ((channel & land) & (field <= MIN_LAND_HEIGHT))
        )
        stats.descent_moved += moved
        stats.descent_climb = max(stats.descent_climb, climb)
    if pad.any():
        field = relief_math.level_pads(field, labels, land, PAD_BLEND_BAND)
        stats.pad_spread = _pad_spread(field, labels)

    result = original.copy()
    rounded = np.clip(np.rint(field), MIN_LAND_HEIGHT, MAX_RELIEF_HEIGHT).astype(np.uint8)
    result[land] = rounded[land]
    stats.step_after = _step_summary(result, land)
    stats.height_changed = int(np.count_nonzero(result != original))
    stats.island_step = _max_step(result, island) if island.any() else 0
    stats.class_slope_before = _class_slope_summary(original, codes, land, names)
    stats.class_slope_after = _class_slope_summary(result, codes, land, names)
    interior = _pad_interior(np.where(land, pad_labels, 0))
    if interior.any():
        stats.pad_slope_before = float(
            np.percentile(relief_math.gradient_magnitude(original)[interior], 95)
        )
        stats.pad_slope_after = float(
            np.percentile(relief_math.gradient_magnitude(result)[interior], 95)
        )
    return result, stats


def _pad_interior(labels: np.ndarray) -> np.ndarray:
    """Return the levelled pixels whose whole Sobel footprint shares their level.

    Slope has to be judged here rather than across the whole province.  A Sobel
    window on a border pixel reaches into the neighbouring relief, so it reports
    the blend ramp - which is meant to be sloped - instead of the ground a model
    actually stands on.
    """

    interior = labels > 0
    for axis in (0, 1):
        for shift in (1, -1):
            interior &= np.roll(labels, shift, axis=axis) == labels
    return interior


def _pad_spread(field: np.ndarray, labels: np.ndarray) -> float:
    """Return the worst height range any single levelled province still carries."""

    worst = 0.0
    for identifier in np.unique(labels[labels > 0]):
        selected = labels == identifier
        worst = max(worst, float(field[selected].max() - field[selected].min()))
    return worst


def _class_slope_summary(
    heights: np.ndarray, codes: np.ndarray, land: np.ndarray, names: Sequence[str]
) -> dict[str, float]:
    """Return the 95th-percentile slope of every declared terrain class.

    This is the readability contract expressed as a number: a province declared
    mountain has to be as steep as a mountain, not merely painted like one.  The
    reference figures are plains 1.03, hills 4.76 and mountains 10.07 height units
    per pixel, so these values say directly whether each class reads correctly.
    """

    slope = relief_math.gradient_magnitude(heights)
    summary: dict[str, float] = {}
    for index, name in enumerate(names):
        selected = land & (codes == index)
        if not selected.any():
            continue
        summary[name] = float(np.percentile(slope[selected], 95))
    return summary


def _peak_ceiling(original: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Return the height ceiling that keeps relief out of the snow line.

    Relief may never push a pixel up into permanent snow, because
    :mod:`tools.builders.build_adiscord_terrain_snow` validates the total snow
    pixel count and would start failing as soon as amplitudes were retuned.  A
    pixel that was already above the threshold keeps its own height as its
    ceiling, which is what stops the clamp from carving a wall around an existing
    peak - the mistake this ceiling replaced.
    """

    return np.where(
        land,
        np.maximum(original.astype(np.float32), np.float32(PEAK_SNOW_HEIGHT - 1)),
        np.float32(MAX_RELIEF_HEIGHT),
    )


def _max_step(heights: np.ndarray, mask: np.ndarray) -> int:
    histogram, pairs, _mean = relief_math.neighbour_step_histogram(heights, mask)
    if not pairs:
        return 0
    return int(np.nonzero(histogram)[0].max())


def _step_summary(heights: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    """Summarise the neighbour-step distribution that measures terracing."""

    histogram, pairs, mean = relief_math.neighbour_step_histogram(heights, mask)
    if not pairs:
        raise RuntimeError("relief statistics need at least one land pixel pair")
    values = np.bincount(heights[mask], minlength=256)
    return {
        "pairs": float(pairs),
        "flat_share": float(histogram[0]) / pairs,
        "gentle_share": float(histogram[1:4].sum()) / pairs,
        "steep_share": float(histogram[4:].sum()) / pairs,
        "mean_step": mean,
        "max_step": float(np.nonzero(histogram)[0].max()),
        "populated_values": float((values > 0).sum()),
        "total_variation": float((histogram * np.arange(histogram.size)).sum()),
    }


def province_corridor(
    channel: frozenset[int],
    province_land: Sequence[int],
    width: int,
    pixel_count: int,
) -> set[int]:
    """Return the widest affordable river corridor inside one city province.

    The channel pixels themselves are always cleared - masonry in the streambed
    is the actual defect.  A one pixel bank is only added while the province
    still keeps :data:`URBAN_CORRIDOR_FLOOR` of its area as readable city, so
    small riverside towns are not erased by their own corridor.
    """

    inside = set(province_land)
    corridor = {index for index in inside if index in channel}
    if not corridor:
        return corridor
    frontier = set(corridor)
    for _step in range(RIVER_CORRIDOR_RADIUS):
        grown = {
            neighbour
            for index in frontier
            for neighbour in neighbours4(index, width, pixel_count)
            if neighbour in inside and neighbour not in corridor
        }
        if not grown:
            break
        remaining = len(inside) - len(corridor) - len(grown)
        if remaining / len(inside) < URBAN_CORRIDOR_FLOOR:
            break
        corridor |= grown
        frontier = grown
    return corridor


def local_slope(
    heights: Sequence[int],
    index: int,
    width: int,
    pixel_count: int,
    water: Sequence[int] | None = None,
) -> int:
    """Return the steepest step to a land neighbour.

    Shoreline pixels sit next to sub-sea-level water, and counting that drop as
    a land slope made every coast score as steep terrain - which painted a
    uniform hill ring around each island.  Water neighbours are skipped.
    """

    steps = [
        abs(heights[index] - heights[neighbour])
        for neighbour in neighbours4(index, width, pixel_count)
        if water is None or not water[neighbour]
    ]
    return max(steps) if steps else 0


def rejected_tree_cells(land: np.ndarray, target: tuple[int, int]) -> np.ndarray:
    """Return the tree cells the canopy must leave empty.

    The inherited layer chose each cell by majority terrain across its footprint,
    so a cell that was 49% ocean still grew trees and its foliage rendered over
    the surf.  Any water in the footprint now rejects the cell outright, which is
    the invariant that matters and is asserted by a regression test.

    The additional inland setback is deliberately partial.  Applying it to every
    shore cell drew a bare belt of constant width around the whole coastline; here
    the first dry ring is cleared only where a coherent noise field says so, so
    the treeline reaches the water in some bays and stands a cell back in others.
    """

    water_share = relief_math.downsampled_fraction(~land, target)
    dry = water_share <= TREE_WATER_TOLERANCE
    inland = relief_math.edge_distance(dry, TREE_COAST_SETBACK + 2)
    ragged = relief_math.striped_field(
        dry.shape,
        lambda xs, ys: relief_math.value_noise(
            xs, ys, TREE_RAGGED_CELL, NOISE_SALT_TREE_EDGE
        ),
    )
    frayed = (inland == TREE_COAST_SETBACK) & (ragged > np.float32(TREE_RAGGED_THRESHOLD))
    return ~dry | (inland < TREE_COAST_SETBACK) | frayed


def build_trees(trees: Image.Image, land: np.ndarray) -> tuple[Image.Image, int, np.ndarray]:
    """Clear every tree cell that overlaps water or crowds the shoreline.

    The canopy is read from the committed pre-setback baseline, not from the layer
    a previous run wrote, so narrowing the setback restores the trees it had
    cleared instead of leaving the widest setback ever applied in place.

    Returns the canopy, the number of cells cleared, and the rejection mask.  The
    mask is the pass's actual claim on ``map/trees.bmp``: this is a purely
    subtractive rule - no cell may carry foliage over water - so the cells it does
    *not* reject are a baseline passthrough that
    :mod:`tools.builders.build_adiscord_province_layer_alignment` is free to plant
    inside its own province scope.
    """

    tree_width, tree_height = trees.size
    rejected = rejected_tree_cells(land, (tree_height, tree_width))
    pixels = load_tree_base(trees)
    if pixels.shape != rejected.shape:
        raise RuntimeError("trees.bmp dimensions do not match the rejection mask")
    permitted = set(np.unique(pixels).tolist()) | {TREE_NONE_INDEX}
    cleared = int(np.count_nonzero(rejected & (pixels != TREE_NONE_INDEX)))
    pixels[rejected] = TREE_NONE_INDEX
    written = set(np.unique(pixels).tolist())
    # This pass only ever clears cells, so it must never introduce an index that
    # the baseline did not already carry.  Every index is a tree *type*; inventing
    # one plants a model the map was never authored with.
    if not written <= permitted:
        raise RuntimeError(
            "trees.bmp would gain tree types that are not in the baseline: "
            f"{sorted(written - permitted)}"
        )
    result = trees.copy()
    result.putdata(pixels.reshape(-1).tolist())
    return result, cleared, rejected


def _rank_signal(declared: str, elevation: float, slope: float) -> float:
    """Return the relief preference of ``declared`` for one pixel."""

    blended = 0.55 * elevation + 0.45 * slope
    if declared == "mountain":
        return blended
    if declared == "hills":
        return 1.0 - abs(blended - 0.52) * 2.0
    if declared == "forest":
        return 0.75 - 0.85 * slope - 0.15 * elevation
    if declared == "plains":
        return 1.0 - blended
    if declared == "marsh":
        return 1.0 - 0.55 * elevation - 1.05 * slope
    if declared == "desert":
        return 1.0 - 0.9 * slope - 0.2 * elevation
    return 1.0 - blended


def _variant(category: str, index: int, width: int, elevation: float, slope: float) -> int:
    """Pick one palette index inside ``category`` for local variety.

    Mountain deliberately never resolves to a single index.  Palette 20 is
    ``mountain_variation_grass`` on texture 7, so a province painted flat 20
    renders as green pasture no matter how high it is - that alone accounted for
    the "mountains look like plains" complaint.  Rock is selected from the local
    slope and elevation against the reference generator's measured class
    boundaries (hills roughly 2-5, mountains 5-10, peaks above 10 units per
    pixel), which is why the same province shows grassy benches, rock faces and
    bare tops instead of one colour.
    """

    options = CATEGORY_PALETTE[category]
    if len(options) == 1:
        return options[0]
    x = index % width
    y = index // width
    noise = warped_fbm(x, y, VARIANT_NOISE_CELL, 7331, octaves=2)
    if category == "mountain":
        rock = 0.62 * slope + 0.38 * elevation + 0.10 * noise
        if rock > MOUNTAIN_PEAK_RANK:
            return options[1]
        if rock > MOUNTAIN_ROCK_RANK:
            return options[2] if len(options) > 2 else options[1]
        return options[0]
    if category == "desert":
        return options[(int((noise + 1.0) * 2.0)) % len(options)]
    return options[1] if noise > 0.42 else options[0]


def _fill_category(elevation: float, slope: float, noise: float, declared: str) -> str:
    """Pick the minority terrain for a pixel that is not the dominant type."""

    blended = 0.55 * elevation + 0.45 * slope
    if blended > 0.74 and declared != "mountain":
        return "mountain"
    if blended > 0.46 and declared != "hills":
        return "hills"
    if declared not in {"forest", "marsh"} and noise > 0.2:
        return "forest"
    if declared == "marsh":
        return "plains"
    if declared in {"desert"}:
        return "hills" if noise > 0.0 else "plains"
    return "plains"


def _neighbour_category(
    codes: np.ndarray,
    names: Sequence[str],
    index: int,
    province: set[int],
    width: int,
    pixel_count: int,
) -> str | None:
    """Return the *declared* land category of an adjacent province, if any.

    This reads ``definition.csv`` through the code field rather than the painted
    neighbour pixel, and that distinction is what makes the repaint converge.
    Reading the paint made two adjacent scope provinces each adopt whatever the
    other had been given on the previous run, so 31 border pixels ping-ponged
    between the two categories - plains and forest, hills and plains - and
    ``map/terrain.bmp`` never reached a fixed point.  The declared terrain cannot
    feed back, and it is also the honest answer to "what is the neighbour": the
    whole point of this pass is that paint should follow the declaration.
    """

    for neighbour in neighbours4(index, width, pixel_count):
        if neighbour in province:
            continue
        code = int(codes[neighbour])
        if code < 0:
            continue
        category = names[code]
        if category in CATEGORY_PALETTE and category != "urban":
            return category
    return None


def repaint_province(
    terrain_pixels: bytearray,
    codes: np.ndarray,
    names: Sequence[str],
    heights: Sequence[int],
    indices: Sequence[int],
    declared: str,
    corridor: frozenset[int],
    water: Sequence[int],
    width: int,
    pixel_count: int,
) -> tuple[set[int], float, float, float]:
    """Repaint one province, returning changes and before/after shares."""

    land = [index for index in indices if terrain_pixels[index] not in WATER_PALETTE]
    if not land:
        raise RuntimeError("province has no land terrain pixels")
    before_share = sum(
        PALETTE_TYPES.get(terrain_pixels[index]) == declared for index in land
    ) / len(land)
    changed: set[int] = set()

    if declared == "urban":
        for index in land:
            if index in corridor:
                value = CATEGORY_PALETTE[CORRIDOR_BANK_CATEGORY][0]
            else:
                value = URBAN_PALETTE
            if terrain_pixels[index] != value:
                terrain_pixels[index] = value
                changed.add(index)
        after_share = sum(
            PALETTE_TYPES.get(terrain_pixels[index]) == declared for index in land
        ) / len(land)
        return changed, before_share, after_share, 0.0

    local = [heights[index] for index in land]
    low = min(local)
    span = max(1, max(local) - low)
    slopes = {
        index: local_slope(heights, index, width, pixel_count, water) for index in land
    }
    steepest = max(1, max(slopes.values()))
    mean_slope = sum(slopes.values()) / len(slopes)
    province = set(indices)

    scored: list[tuple[float, int]] = []
    for index in land:
        elevation = (heights[index] - low) / span
        slope = slopes[index] / steepest
        x = index % width
        y = index // width
        noise = warped_fbm(x, y, TERRAIN_NOISE_CELL, 7211, octaves=3)
        signal = _rank_signal(declared, elevation, slope) + TERRAIN_NOISE_WEIGHT * noise
        scored.append((-signal, index))
    scored.sort()
    target = min(len(land), ceil(len(land) * DOMINANT_SHARE.get(declared, 0.75)))
    dominant = {index for _signal, index in scored[:target]}

    for index in land:
        elevation = (heights[index] - low) / span
        slope = slopes[index] / steepest
        if index in dominant:
            category = declared
        else:
            x = index % width
            y = index // width
            noise = warped_fbm(x, y, TERRAIN_NOISE_CELL, 7211, octaves=3)
            # Minority pixels on a province seam adopt the neighbour's terrain
            # so the two provinces interleave instead of butting against a
            # clean polygon edge.
            adopted = _neighbour_category(
                codes, names, index, province, width, pixel_count
            )
            if adopted is not None and noise > -0.25:
                category = adopted
            else:
                category = _fill_category(elevation, slope, noise, declared)
        if index in corridor and category == "urban":
            category = CORRIDOR_BANK_CATEGORY
        value = _variant(category, index, width, elevation, slope)
        if terrain_pixels[index] != value:
            terrain_pixels[index] = value
            changed.add(index)

    after_share = sum(
        PALETTE_TYPES.get(terrain_pixels[index]) == declared for index in land
    ) / len(land)
    return changed, before_share, after_share, mean_slope


def _declared_share(
    terrain_pixels: Sequence[int], indices: Sequence[int], declared: str
) -> float:
    """Return the share of a province's visible land that reads as ``declared``."""

    land = [index for index in indices if terrain_pixels[index] not in WATER_PALETTE]
    if not land:
        raise RuntimeError("province has no land terrain pixels")
    return sum(
        PALETTE_TYPES.get(terrain_pixels[index]) == declared for index in land
    ) / len(land)


def _seam_row_share(terrain_pixels: Sequence[int], width: int) -> float:
    """Return the share of land pixels whose index changes across the seam row.

    This is the number the straight line *is*: the neighbouring rows sit at 7-12%
    and the seam row sat at 31%, so the metric says directly whether the boundary
    still resolves in a single step.
    """

    above = NORTHERN_SEAM_ROW - 1
    if above < 0:
        return 0.0
    changed = 0
    land = 0
    for column in range(width):
        first = terrain_pixels[above * width + column]
        second = terrain_pixels[NORTHERN_SEAM_ROW * width + column]
        if first in WATER_PALETTE and second in WATER_PALETTE:
            continue
        land += 1
        if first != second:
            changed += 1
    return changed / land if land else 0.0


def cold_band_strength(heights: np.ndarray, land: np.ndarray) -> np.ndarray:
    """Return how arctic each land pixel is: 1 at the ice cap, 0 south of the band.

    The reference edge is
    :func:`tools.builders.build_adiscord_terrain_snow.polar_cap_boundary`, split
    into its column and elevation terms so this pass tracks the permanent-snow
    line instead of a latitude of its own.  Because the elevation term is part of
    it, the cold band bulges south over high ground and retreats up the valleys,
    exactly like the snow line it follows.
    """

    map_height, width = heights.shape
    rows = min(
        map_height,
        snow.POLAR_CAP_Y
        + snow.POLAR_CAP_GENERATED_OFFSET
        + snow.POLAR_CAP_LONG_AMPLITUDE
        + snow.POLAR_CAP_MEDIUM_AMPLITUDE
        + snow.POLAR_CAP_DETAIL_AMPLITUDE
        + snow.POLAR_CAP_RELIEF_MAX
        + COLD_BAND_DEPTH,
    )
    strength = np.zeros(heights.shape, dtype=np.float32)
    if rows <= 0:
        return strength
    longitude = np.array(
        [snow.polar_cap_longitude(x) for x in range(width)], dtype=np.float32
    )
    relief = np.clip(
        (heights[:rows].astype(np.float32) - np.float32(100.0))
        * np.float32(snow.POLAR_CAP_RELIEF_SCALE),
        np.float32(snow.POLAR_CAP_RELIEF_MIN),
        np.float32(snow.POLAR_CAP_RELIEF_MAX),
    )
    boundary = (
        np.float32(snow.POLAR_CAP_Y + snow.POLAR_CAP_GENERATED_OFFSET)
        + longitude[None, :]
        + relief
    )
    depth = np.arange(rows, dtype=np.float32)[:, None] - boundary
    strength[:rows] = np.clip(
        np.float32(1.0) - depth / np.float32(COLD_BAND_DEPTH), 0.0, 1.0
    )
    return np.where(land, strength, np.float32(0.0))


def cool_northern_palette(
    terrain_pixels: bytearray, heights: np.ndarray, land: np.ndarray
) -> tuple[set[int], Counter[int]]:
    """Swap warm-reading textures for cold ones inside the arctic band.

    Returns the pixels written and a count per substituted palette index.
    Idempotent by construction: no value on the right-hand side of
    :data:`COLD_PALETTE_SUBSTITUTION` is also a key, so a second run finds
    nothing left to substitute.
    """

    strength = cold_band_strength(heights, land)
    populated = np.nonzero(strength.any(axis=1))[0]
    if populated.size == 0:
        return set(), Counter()
    rows = int(populated[-1]) + 1
    width = strength.shape[1]
    noise = relief_math.striped_field(
        (rows, width),
        lambda xs, ys: relief_math.warped_fbm(
            xs, ys, COLD_BAND_NOISE_CELL, NOISE_SALT_COLD_BAND, octaves=2
        ),
    )
    cold = strength[:rows] > (
        np.float32(COLD_BAND_BIAS) + np.float32(COLD_BAND_NOISE_WEIGHT) * noise
    )
    strip = np.frombuffer(
        bytes(terrain_pixels[: rows * width]), dtype=np.uint8
    ).reshape(rows, width)
    updated = strip.copy()
    for warm, cool in sorted(COLD_PALETTE_SUBSTITUTION.items()):
        updated[cold & (strip == warm)] = cool
    flat_before = strip.reshape(-1)
    flat_after = updated.reshape(-1)
    moved = np.nonzero(flat_after != flat_before)[0]
    substituted: Counter[int] = Counter()
    for index in moved.tolist():
        substituted[int(flat_before[index])] += 1
        terrain_pixels[index] = int(flat_after[index])
    return set(moved.tolist()), substituted


def northern_seam_band(height: int) -> range:
    """Return the rows the seam dissolve may write, widest band included."""

    if NORTHERN_SEAM_ROW - NORTHERN_SEAM_DEPTH - 1 < 0:
        return range(0)
    if NORTHERN_SEAM_ROW + NORTHERN_SEAM_DEPTH >= height:
        return range(0)
    return range(
        NORTHERN_SEAM_ROW - NORTHERN_SEAM_DEPTH,
        NORTHERN_SEAM_ROW + NORTHERN_SEAM_DEPTH,
    )


def dissolve_northern_seam(
    terrain_pixels: bytearray, heights: Sequence[int], width: int, height: int
) -> set[int]:
    """Interleave the inherited single-row index seam into tongues and pockets.

    Snow indices are folded back to their base terrain before the comparison, so
    a column whose northern anchor is currently permanent snow is matched against
    the terrain underneath it rather than against the white paint on top.

    Pixels the permanent-snow classifier would paint white are then skipped
    outright, and that exclusion is what makes this pass a fixed point rather than
    a mere convenience.  ``RESTORE_SNOW`` maps both snow indices back to a single
    representative each - 19 to plains and 16 to rocky mountain - so a hills pixel
    that snow covered would come back as plains on the next run and the dissolve
    would keep moving it.  Inside the cap the visible boundary is the snow edge
    anyway, and that belongs to
    :mod:`tools.builders.build_adiscord_terrain_snow`, whose own graded transition
    band handles it.
    """

    band = northern_seam_band(height)
    if not band:
        return set()
    depth = NORTHERN_SEAM_DEPTH
    first = band.start - 1
    strip = np.frombuffer(
        bytes(terrain_pixels[first * width : (band.stop + 1) * width]), dtype=np.uint8
    ).reshape(2 * depth + 2, width)
    base = strip.copy()
    for snowy, restored in sorted(snow.RESTORE_SNOW.items()):
        base[strip == snowy] = restored
    north = base[0].astype(np.int16)
    south = base[-1].astype(np.int16)
    water = np.array(sorted(WATER_PALETTE), dtype=np.int16)
    acting = (
        (north != south)
        & ~np.isin(north, water)
        & ~np.isin(south, water)
        & (north != np.int16(URBAN_PALETTE))
        & (south != np.int16(URBAN_PALETTE))
    )
    if not acting.any():
        return set()

    # The boundary is placed explicitly rather than derived from a threshold
    # ramp.  A ramp was the first attempt and it barely moved the line: the
    # threshold climbs by 1/(2*depth) per row while the noise only deviates by
    # about a quarter, so the crossing could never travel more than two rows from
    # the centre and the seam row kept 31% of its changes.  Giving each column its
    # own edge row spreads the crossings across the whole band instead, which is
    # what stops any single row from carrying the transition.
    columns = np.arange(width, dtype=np.float32)
    zeros = np.zeros(width, dtype=np.float32)
    scale = np.float32(NORTHERN_SEAM_MIN_SCALE) + np.float32(
        1.0 - NORTHERN_SEAM_MIN_SCALE
    ) * (
        np.float32(0.5)
        + np.float32(0.5)
        * relief_math.value_noise(
            columns, zeros, NORTHERN_SEAM_WIDTH_CELL, NOISE_SALT_SEAM_WIDTH
        )
    )
    local = np.maximum(np.float32(1.0), np.float32(depth) * scale)
    # ``value_noise`` interpolates uniform lattice hashes, so its own
    # distribution is bell shaped and would pile the edges back up near the
    # centre.  Reshaping it towards the band limits is what makes the residual at
    # any one row roughly the band average rather than a spike.
    wiggle = relief_math.value_noise(
        columns, zeros, NORTHERN_SEAM_EDGE_CELL, NOISE_SALT_SEAM_EDGE
    )
    wiggle = np.sign(wiggle) * np.power(
        np.abs(wiggle), np.float32(NORTHERN_SEAM_EDGE_SHAPE)
    )
    edge = np.float32(NORTHERN_SEAM_ROW) + (local - np.float32(0.5)) * wiggle
    pocket = relief_math.striped_field(
        (len(band), width),
        lambda xs, ys: relief_math.warped_fbm(
            xs,
            ys + np.float32(band.start),
            NORTHERN_SEAM_DETAIL_CELL,
            NOISE_SALT_SEAM_DETAIL,
            octaves=2,
        ),
    )

    snowy = frozenset({snow.SNOW_MOUNTAIN, snow.SNOW_PLAIN})
    changed: set[int] = set()
    for offset, row in enumerate(band):
        southward = (
            np.float32(row) + np.float32(0.5) - edge
            + local * np.float32(NORTHERN_SEAM_NOISE_WEIGHT) * pocket[offset]
        ) > np.float32(0.0)
        target = np.where(southward, south, north)
        current = base[offset + 1].astype(np.int16)
        eligible = (current == north) | (current == south)
        write = acting & eligible & (target != current)
        for column in np.nonzero(write)[0].tolist():
            index = row * width + column
            elevation = heights[index]
            if any(
                snow.classify_terrain(int(candidate[column]), row, elevation, column)
                in snowy
                for candidate in (north, south)
            ):
                continue
            terrain_pixels[index] = int(target[column])
            changed.add(index)
    return changed


def normalise_snow(
    terrain_pixels: bytearray,
    heights: Sequence[int],
    touched: Sequence[int],
    width: int,
) -> None:
    """Hand every written pixel back to the permanent-snow classifier."""

    for index in touched:
        value = terrain_pixels[index]
        if value in WATER_PALETTE:
            continue
        terrain_pixels[index] = snow.classify_terrain(
            value, index // width, heights[index], index % width
        )


def _assert_sea_level_contract(
    heights: np.ndarray, land: np.ndarray, require_land_floor: bool
) -> None:
    """Fail loudly if the land/sea height contract does not hold.

    Three places in this repository used to disagree about sea level, and one of
    them clamped land down to 89 - the value that *is* water.  Asserting one
    contract on both sides of the pass is what makes a global relief pass safe:
    every pixel ``definition.csv`` calls water stays at exactly
    :data:`WATER_HEIGHT`, and every land pixel ends at or above
    :data:`MIN_LAND_HEIGHT`.

    The land floor is only required *after* the pass.  The inherited raster has a
    single declared-land pixel stored at water depth (province 16652), which this
    builder repairs; gameplay land and sea come from ``definition.csv``, so that
    pixel was only ever a rendering artefact.
    """

    if MIN_LAND_HEIGHT <= SEA_LEVEL:
        raise RuntimeError("the land minimum must sit above sea level")
    water_values = np.unique(heights[~land])
    if water_values.tolist() != [WATER_HEIGHT]:
        raise RuntimeError(
            f"map/heightmap.bmp: water must be exactly {WATER_HEIGHT}, found "
            f"{water_values.tolist()[:8]}"
        )
    if require_land_floor:
        lowest = int(heights[land].min())
        if lowest < MIN_LAND_HEIGHT:
            raise RuntimeError(
                f"map/heightmap.bmp: land must stay at or above {MIN_LAND_HEIGHT}, "
                f"found {lowest}"
            )


def build_expected() -> BuildOutputs:
    scope = load_scope()
    definition = read_definition(DEFINITION_PATH)
    pad_ids = sorted(
        PAD_PROVINCE_IDS
        | {
            province_id
            for province_id, row in definition.items()
            if row.is_land and row.terrain in PAD_TERRAIN
        }
    )
    wanted = terrain_province_ids(scope) | relief_province_ids(scope) | set(pad_ids)
    for province_id in sorted(wanted):
        row = definition.get(province_id)
        if row is None:
            raise RuntimeError(f"definition.csv: scope province {province_id} is missing")
        if not row.is_land:
            raise RuntimeError(f"province {province_id}: readability scope requires a land province")

    with Image.open(BytesIO(PROVINCES_PATH.read_bytes())) as provinces:
        if provinces.size != (5632, 2048) and provinces.size[0] < 2:
            raise RuntimeError("provinces.bmp is unexpectedly small")
        indices_by_province, water = province_pixel_index(provinces, definition, wanted)
        codes, land, category_names = terrain_code_field(provinces, definition)
        width, height = provinces.size
    pixel_count = width * height

    with Image.open(BytesIO(TERRAIN_PATH.read_bytes())) as terrain_source:
        terrain = terrain_source.copy()
    with Image.open(BytesIO(HEIGHTMAP_PATH.read_bytes())) as height_source:
        heightmap = height_source.copy()
    with Image.open(BytesIO(WORLD_NORMAL_PATH.read_bytes())) as normal_source:
        world_normal = normal_source.copy()
    with Image.open(BytesIO(TREES_PATH.read_bytes())) as tree_source:
        trees = tree_source.copy()
    if (
        terrain.mode != "P"
        or heightmap.mode != "L"
        or world_normal.mode != "RGB"
        or trees.mode != "P"
    ):
        raise RuntimeError("unexpected map bitmap modes")
    if terrain.size != (width, height) or heightmap.size != (width, height):
        raise RuntimeError("terrain/heightmap/provinces dimensions differ")
    if (world_normal.size[0] * 2, world_normal.size[1] * 2) != (width, height):
        raise RuntimeError("world_normal.bmp must be half the heightmap dimensions")

    with Image.open(BytesIO(RIVERS_PATH.read_bytes())) as rivers:
        if rivers.size != (width, height):
            raise RuntimeError("rivers.bmp dimensions differ from provinces.bmp")
        channel = frozenset(river_corridor_indices(rivers, 0))
    corridor: set[int] = set()
    for province_id in sorted(scope["urban_river_provinces"]):
        corridor |= province_corridor(
            channel, indices_by_province[province_id], width, pixel_count
        )
    corridor = frozenset(corridor)

    height_array = load_relief_base(heightmap)
    _assert_sea_level_contract(height_array, land, require_land_floor=False)
    island = np.zeros(land.shape, dtype=bool)
    island_flat = island.reshape(-1)
    for province_id in sorted(scope["northern_island_provinces"]):
        for index in indices_by_province[province_id]:
            island_flat[index] = True
    island &= land
    if not island.any():
        raise RuntimeError("northern island scope resolved to no land pixels")

    channel_mask = np.zeros(land.shape, dtype=bool)
    channel_flat = channel_mask.reshape(-1)
    for index in channel:
        channel_flat[index] = True
    for province_id in pad_ids:
        if province_id not in indices_by_province:
            raise RuntimeError(f"levelled province {province_id} is not on the map")
    pad_labels = np.zeros(land.shape, dtype=np.int32)
    pad_label_flat = pad_labels.reshape(-1)
    for label, province_id in enumerate(pad_ids, start=1):
        for index in indices_by_province.get(province_id, ()):
            pad_label_flat[index] = label

    height_array, relief = build_global_relief(
        height_array, land, codes, category_names, island, channel_mask, pad_labels
    )
    relief.pad_provinces = len(pad_ids)
    _assert_sea_level_contract(height_array, land, require_land_floor=True)
    heightmap = Image.fromarray(height_array, mode="L")
    # Plain bytes rather than the array: indexing a uint8 array yields uint8, and
    # the terrain repaint subtracts neighbouring heights, which would wrap.
    heights = height_array.tobytes()

    terrain_pixels = bytearray(terrain.tobytes())
    stats = TerrainStats()
    # The seam dissolve runs *before* the province repaint.  Running it after put
    # province 959 below its declared-hills floor, because the dissolve was
    # reassigning pixels the repaint had already counted towards the province's
    # dominant share.  Ahead of the repaint the two cooperate instead: the
    # dissolve breaks the inherited line everywhere, and each scope province then
    # re-establishes its own dominance over the result.
    stats.seam_share_before = _seam_row_share(terrain_pixels, width)
    interleaved = dissolve_northern_seam(terrain_pixels, heights, width, height)
    stats.seam_interleaved = len(interleaved)
    stats.changed |= interleaved

    neighbour_codes = codes.reshape(-1)
    for province_id in sorted(terrain_province_ids(scope)):
        declared = definition[province_id].terrain
        if declared in UNPAINTABLE_TERRAIN:
            continue
        if declared not in DOMINANT_SHARE:
            raise RuntimeError(
                f"province {province_id}: unsupported declared terrain {declared!r}"
            )
        changed, before, after, mean_slope = repaint_province(
            terrain_pixels, neighbour_codes, category_names, heights,
            indices_by_province[province_id], declared, corridor, water,
            width, pixel_count,
        )
        stats.changed |= changed
        stats.declared[province_id] = declared
        stats.share_before[province_id] = before
        stats.share_after[province_id] = after
        stats.slope_after[province_id] = mean_slope
        cleared = sum(
            1 for index in indices_by_province[province_id] if index in corridor
        )
        if declared == "urban" and cleared:
            stats.corridor_cleared += cleared
            stats.corridor_provinces.add(province_id)

    # The palette temperature pass runs last of the three, because the repaint's
    # own ``_variant`` emits ``mountain_variation_grass`` and an earlier pass
    # would leave that green in place.  It is safe there precisely because every
    # substitution keeps the terrain category, so it cannot move a share the
    # repaint just satisfied.
    cooled, stats.cold_substituted = cool_northern_palette(
        terrain_pixels, height_array, land
    )
    stats.changed |= cooled

    # Shares are re-measured from the finished raster so the contract below is
    # asserted against what actually ships, and *before* the snow classifier
    # because a white polar pixel carries the category of the terrain under the
    # paint rather than the biome its province declares.
    for province_id in sorted(stats.share_after):
        declared = stats.declared[province_id]
        stats.share_after[province_id] = _declared_share(
            terrain_pixels, indices_by_province[province_id], declared
        )

    normalise_snow(terrain_pixels, heights, sorted(stats.changed), width)
    # Measured on the finished band, because the white paint the classifier lays
    # over the cap is part of what the player sees at the seam row.
    stats.seam_share_after = _seam_row_share(terrain_pixels, width)
    generated_terrain = terrain.copy()
    generated_terrain.putdata(terrain_pixels)

    claim = np.zeros(width * height, dtype=bool)
    for province_id in sorted(terrain_province_ids(scope)):
        for index in indices_by_province[province_id]:
            claim[index] = True
    northern = cold_band_strength(height_array, land) > 0.0
    claim |= northern.reshape(-1)
    for row in northern_seam_band(height):
        claim[row * width:(row + 1) * width] = True
    claim &= land.reshape(-1)

    normal_array = relief_math.encode_world_normal(
        height_array,
        (world_normal.size[1], world_normal.size[0]),
        NORMAL_SOBEL_FACTOR,
        NORMAL_BLUE,
    )
    previous_normal = np.asarray(world_normal, dtype=np.uint8)
    normal_changed = int(np.count_nonzero((previous_normal != normal_array).any(axis=2)))
    generated_normal = Image.fromarray(normal_array, mode="RGB")

    generated_trees, trees_cleared, tree_claim = build_trees(trees, land)
    return BuildOutputs(
        heightmap,
        generated_normal,
        generated_terrain,
        generated_trees,
        relief,
        stats,
        normal_changed,
        trees_cleared,
        claim,
        tree_claim.reshape(-1),
    )


def _issues(outputs: BuildOutputs) -> list[str]:
    issues: list[str] = []
    # ``heightmap`` and ``world_normal`` are rebuilt globally, so the whole file is
    # this builder's to compare.  ``terrain`` and ``trees`` are not: the repaint
    # covers a frozen province scope plus the northern band, the tree pass is a
    # subtractive shoreline rule, and
    # :mod:`tools.builders.build_adiscord_province_layer_alignment` owns 47
    # provinces of its own and writes both layers after this pass.  Comparing
    # every byte therefore reported that builder's legitimate output as our drift.
    claims = {TERRAIN_PATH: outputs.terrain_claim, TREES_PATH: outputs.tree_claim}
    for path, image in (
        (HEIGHTMAP_PATH, outputs.heightmap),
        (WORLD_NORMAL_PATH, outputs.world_normal),
        (TERRAIN_PATH, outputs.terrain),
        (TREES_PATH, outputs.trees),
    ):
        with Image.open(BytesIO(path.read_bytes())) as current:
            if current.mode != image.mode or current.size != image.size:
                issues.append(f"{path.relative_to(ROOT).as_posix()}: mode or dimensions differ")
                continue
            current_bytes = np.frombuffer(current.tobytes(), dtype=np.uint8)
            expected_bytes = np.frombuffer(image.tobytes(), dtype=np.uint8)
            claim = claims.get(path)
            if claim is None:
                differing = current_bytes != expected_bytes
            else:
                differing = (current_bytes != expected_bytes) & claim
            differences = int(np.count_nonzero(differing))
            if differences:
                scope = "" if claim is None else " claimed"
                issues.append(
                    f"{path.relative_to(ROOT).as_posix()}: {differences} generated"
                    f"{scope} bytes differ"
                )
            if current.mode == "P" and current.getpalette() != image.getpalette():
                issues.append(f"{path.relative_to(ROOT).as_posix()}: palette differs")
    after = outputs.relief.step_after
    if after["max_step"] > MAX_ANY_STEP:
        issues.append(
            f"map/heightmap.bmp: a land step of {after['max_step']:.0f} units exceeds "
            f"the {MAX_ANY_STEP} unit ceiling"
        )
    if outputs.relief.pad_spread > MAX_PAD_SPREAD:
        issues.append(
            "map/heightmap.bmp: a levelled province varies by "
            f"{outputs.relief.pad_spread:.0f} units and must be level"
        )
    if outputs.relief.pad_slope_after > MAX_URBAN_SLOPE:
        issues.append(
            f"map/heightmap.bmp: levelled ground reaches "
            f"{outputs.relief.pad_slope_after:.2f} units per pixel and must stay "
            f"under {MAX_URBAN_SLOPE} so building models sit level"
        )
    # The de-quantisation contract.  A heightmap on a coarse ladder cannot show a
    # gentle slope at all, so these three numbers gate every other relief claim.
    if after["flat_share"] > MAX_FLAT_SHARE:
        issues.append(
            f"map/heightmap.bmp: {after['flat_share']:.3f} of neighbouring land "
            f"pixels are still identical (ceiling {MAX_FLAT_SHARE:.2f}), so the "
            "surface is still terraced"
        )
    if after["gentle_share"] < MIN_GENTLE_SHARE:
        issues.append(
            f"map/heightmap.bmp: only {after['gentle_share']:.3f} of land steps are "
            f"1-3 units (floor {MIN_GENTLE_SHARE:.2f}), so gentle slopes are missing"
        )
    if after["populated_values"] < MIN_POPULATED_HEIGHTS:
        issues.append(
            f"map/heightmap.bmp: only {after['populated_values']:.0f} distinct land "
            f"elevations are populated (floor {MIN_POPULATED_HEIGHTS})"
        )
    for name, floor in MIN_CLASS_SLOPE.items():
        measured = outputs.relief.class_slope_after.get(name)
        if measured is not None and measured < floor:
            issues.append(
                f"map/heightmap.bmp: provinces declared {name} reach only a "
                f"{measured:.2f} unit-per-pixel slope (floor {floor:.2f}), so they "
                f"do not read as {name}"
            )
    if outputs.relief.island_step > MAX_ISLAND_STEP:
        issues.append(
            f"map/heightmap.bmp: the northern island still has a "
            f"{outputs.relief.island_step} unit step (limit {MAX_ISLAND_STEP})"
        )
    for province_id, share in sorted(outputs.terrain_stats.share_after.items()):
        declared = outputs.terrain_stats.declared[province_id]
        floor = MINIMUM_SHARE[declared]
        if share < floor:
            issues.append(
                f"map/terrain.bmp: province {province_id} declared {declared} but only "
                f"{share:.2f} of its visible area reads as {declared} (floor {floor:.2f})"
            )
    return issues


def validate() -> list[str]:
    return _issues(build_expected())


def apply() -> BuildOutputs:
    outputs = build_expected()
    save_bitmap_atomically(outputs.heightmap, HEIGHTMAP_PATH)
    save_bitmap_atomically(outputs.world_normal, WORLD_NORMAL_PATH)
    save_bitmap_atomically(outputs.terrain, TERRAIN_PATH)
    save_bitmap_atomically(outputs.trees, TREES_PATH)
    return outputs


def _report(outputs: BuildOutputs) -> None:
    before = outputs.relief.step_before
    after = outputs.relief.step_after
    print(
        "Relief and readability applied: "
        f"{outputs.relief.height_changed} height pixels, "
        f"{outputs.normal_changed} normal cells, "
        f"{len(outputs.terrain_stats.changed)} terrain pixels, "
        f"{outputs.trees_cleared} tree cells pulled off the coast, "
        f"{outputs.terrain_stats.corridor_cleared} river-corridor pixels across "
        f"{len(outputs.terrain_stats.corridor_provinces)} city provinces."
    )
    print("Land neighbour-step distribution (the de-quantisation evidence):")
    for label, key, form in (
        ("identical neighbours", "flat_share", "{:.3f}"),
        ("gentle steps 1-3", "gentle_share", "{:.3f}"),
        ("steep steps >=4", "steep_share", "{:.3f}"),
        ("mean step", "mean_step", "{:.3f}"),
        ("maximum step", "max_step", "{:.0f}"),
        ("populated elevations", "populated_values", "{:.0f}"),
        ("total variation", "total_variation", "{:,.0f}"),
    ):
        print(
            f"  {label:22s} "
            f"{form.format(before[key])} -> {form.format(after[key])}"
        )
    stats = outputs.terrain_stats
    print(
        "Northern band: "
        f"seam row y={NORTHERN_SEAM_ROW} land index changes "
        f"{stats.seam_share_before:.1%} -> {stats.seam_share_after:.1%} "
        f"({stats.seam_interleaved} pixels interleaved)"
    )
    if stats.cold_substituted:
        detail = ", ".join(
            f"{warm}->{COLD_PALETTE_SUBSTITUTION[warm]}: {count}"
            for warm, count in sorted(stats.cold_substituted.items())
        )
        print(f"  cold palette substitutions {sum(stats.cold_substituted.values())} ({detail})")
    print(f"  northern island max step   -> {outputs.relief.island_step}")
    print(f"  gradient cap moved         {outputs.relief.gradient_moved} pixels")
    print(
        f"  river descent lowered      {outputs.relief.descent_moved} channel pixels, "
        f"worst climb removed {outputs.relief.descent_climb:.0f} units"
    )
    print(
        f"  levelled provinces         {outputs.relief.pad_provinces}, "
        f"worst height spread {outputs.relief.pad_spread:.0f} units"
    )
    print(
        f"  levelled interior slope    {outputs.relief.pad_slope_before:.2f} -> "
        f"{outputs.relief.pad_slope_after:.2f} units per pixel"
    )
    print("95th-percentile slope per declared terrain (units per pixel):")
    for name in sorted(outputs.relief.class_slope_after):
        reference = REFERENCE_CLASS_SLOPE.get(name)
        suffix = f"   (reference {reference:.2f})" if reference else ""
        print(
            f"  {name:22s} "
            f"{outputs.relief.class_slope_before.get(name, 0.0):6.2f} -> "
            f"{outputs.relief.class_slope_after[name]:6.2f}{suffix}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--apply", action="store_true", help="write the relief and terrain layers")
    action.add_argument("--check", action="store_true", help="validate generated outputs (default)")
    action.add_argument(
        "--seed-base",
        action="store_true",
        help="capture the current map/heightmap.bmp as the pre-relief baseline",
    )
    args = parser.parse_args()
    if args.seed_base:
        written = seed_relief_base()
        for name in written:
            print(f"Captured {name}.")
        if not written:
            print("Both relief baselines already exist; nothing captured.")
        return 0
    if args.apply:
        outputs = apply()
        _report(outputs)
        issues = _issues(outputs)
    else:
        outputs = build_expected()
        _report(outputs)
        issues = _issues(outputs)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Map relief and terrain readability validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
