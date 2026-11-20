"""Render Svetlogorye's basin from native geography and bind its map markers."""

from __future__ import annotations

import argparse
import csv
import io
import math
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from tools.lib.paths import repository_root


ROOT = repository_root()
OUT = Path("gfx/interface/NAM_basin")
WIDTH, HEIGHT = 436, 246
STATES = (67, 688, 689, 690, 719, 700)
GUI = Path("interface/ADISCORD_NAM_basin.gui")
GFX = Path("interface/ADISCORD_NAM_basin.gfx")
BEGIN = "# BEGIN GENERATED NAM BASIN MAP"
END = "# END GENERATED NAM BASIN MAP"
COLOURS = ((60, 150, 143, 68), (190, 78, 65, 115), (110, 116, 121, 110))
CATEGORY_PICTURE_GAP = 12


def pack_rgb(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.int32)
    return values[..., 0] * 65536 + values[..., 1] * 256 + values[..., 2]


def read_geography(states: tuple[int, ...] = STATES) -> tuple[np.ndarray, dict[int, set[int]], set[int]]:
    province_colours = {}
    land_colours = set()
    with (ROOT / "map/definition.csv").open(encoding="utf-8-sig") as source:
        for row in csv.reader(source, delimiter=";"):
            if len(row) < 5 or not row[0].isdigit():
                continue
            colour = int(row[1]) * 65536 + int(row[2]) * 256 + int(row[3])
            province_colours[int(row[0])] = colour
            if row[4] == "land":
                land_colours.add(colour)
    state_colours = {}
    for state in states:
        paths = sorted((ROOT / "history/states").glob(f"{state}-*.txt"))
        if len(paths) != 1:
            raise ValueError(f"Expected one state history for {state}")
        source = paths[0].read_text(encoding="utf-8-sig")
        match = re.search(r"provinces\s*=\s*\{([^}]+)\}", source)
        if not match:
            raise ValueError(f"Missing provinces in state {state}")
        state_colours[state] = {province_colours[int(p)] for p in re.findall(r"\d+", match[1])}
    with Image.open(ROOT / "map/provinces.bmp") as source:
        provinces = pack_rgb(np.asarray(source.convert("RGB")))
    return provinces, state_colours, land_colours


def interior_anchor(mask: Image.Image) -> tuple[int, int]:
    """Anchor tiny coastal states inside their actual outline, never at a sea centroid."""
    inner = mask
    while True:
        eroded = inner.filter(ImageFilter.MinFilter(3))
        if not eroded.getbbox():
            break
        inner = eroded
    y, x = np.where(np.asarray(inner) > 0)
    distance = (x - x.mean()) ** 2 + (y - y.mean()) ** 2
    index = int(np.argmin(distance))
    return int(x[index]), int(y[index])


def map_images() -> tuple[dict[str, Image.Image], dict[int, dict]]:
    provinces, state_colours, land_colours = read_geography()
    selected = np.isin(provinces, list(set.union(*state_colours.values())))
    y, x = np.where(selected)
    box = (max(0, int(x.min()) - 15), max(0, int(y.min()) - 12),
           min(provinces.shape[1], int(x.max()) + 16), min(provinces.shape[0], int(y.max()) + 13))
    # Fill the viewport with geographic context instead of drawing a false
    # coastline at a letterboxed crop edge.
    crop_width = box[2] - box[0]
    crop_height = box[3] - box[1]
    extra_width = max(0, math.ceil(crop_height * WIDTH / HEIGHT) - crop_width)
    extra_height = max(0, math.ceil(crop_width * HEIGHT / WIDTH) - crop_height)
    box = (box[0] - extra_width // 2, box[1] - extra_height // 2,
           box[2] + extra_width - extra_width // 2, box[3] + extra_height - extra_height // 2)
    crop = provinces[box[1]:box[3], box[0]:box[2]]
    size = (WIDTH, HEIGHT)

    def fitted(array: np.ndarray, resample=Image.Resampling.NEAREST) -> Image.Image:
        image = Image.fromarray(array).resize(size, resample)
        return image

    land = fitted(np.isin(crop, list(land_colours)).astype(np.uint8) * 255)
    with Image.open(ROOT / "map/heightmap.bmp") as source:
        elevation = fitted(np.asarray(source.convert("L").crop(box)), Image.Resampling.BILINEAR)
    heights = np.asarray(elevation).astype(float)
    dy, dx = np.gradient(heights)
    shade = np.clip((heights - 100) * 0.21 - dx * 1.2 - dy * 0.8, -12, 38)
    pixels = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
    land_pixels = np.asarray(land) > 0
    for channel, base in enumerate((48, 57, 55)):
        pixels[..., channel] = np.where(land_pixels, np.clip(base + shade, 0, 255), (18, 35, 43)[channel])
    pixels[..., 3] = 255
    background = Image.fromarray(pixels)
    contours = np.asarray(elevation) // 8
    contour = np.zeros((HEIGHT, WIDTH), dtype=bool)
    contour[1:] |= contours[1:] != contours[:-1]
    contour[:, 1:] |= contours[:, 1:] != contours[:, :-1]
    contour &= land_pixels
    contour_mask = Image.fromarray(contour.astype(np.uint8) * 34)
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (191, 180, 142)),
                                              Image.new("RGBA", background.size), contour_mask))
    coastline = ImageChops.subtract(land.filter(ImageFilter.MaxFilter(5)), land)
    background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (68, 106, 111, 180)),
                                              Image.new("RGBA", background.size), coastline))
    grid = Image.new("RGBA", background.size)
    drawing = ImageDraw.Draw(grid)
    for gx in range(20, WIDTH, 40):
        drawing.line((gx, 0, gx, HEIGHT), fill=(183, 185, 157, 22))
    for gy in range(8, HEIGHT, 40):
        drawing.line((0, gy, WIDTH, gy), fill=(183, 185, 157, 22))
    background.alpha_composite(grid)
    geometry = {}
    images = {"map.png": background}
    for state in STATES:
        mask = fitted(np.isin(crop, list(state_colours[state])).astype(np.uint8) * 255)
        anchor = interior_anchor(mask)
        geometry[state] = {"mask": mask, "anchor": anchor}
        edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
        background.alpha_composite(Image.composite(Image.new("RGBA", background.size, (166, 156, 113, 210)),
                                                  Image.new("RGBA", background.size), edge))
        strip = Image.new("RGBA", (WIDTH * 4, HEIGHT))
        for frame, colour in enumerate(COLOURS):
            overlay = Image.composite(Image.new("RGBA", mask.size, colour), Image.new("RGBA", mask.size), mask)
            strip.paste(overlay, (frame * WIDTH, 0))
        selection = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask.filter(ImageFilter.MinFilter(3)))
        overlay = Image.composite(Image.new("RGBA", mask.size, (241, 204, 120, 255)), Image.new("RGBA", mask.size), selection)
        strip.paste(overlay, (WIDTH * 3, 0))
        images[f"state_{state}.png"] = strip
    drawing = ImageDraw.Draw(background)
    drawing.rectangle((0, 0, WIDTH - 1, HEIGHT - 1), outline=(128, 119, 90))
    drawing.rectangle((3, 3, WIDTH - 4, HEIGHT - 4), outline=(56, 72, 72))
    drawing.line((WIDTH - 25, 22, WIDTH - 25, 62), fill=(203, 186, 139), width=1)
    drawing.line((WIDTH - 36, 42, WIDTH - 14, 42), fill=(203, 186, 139), width=1)
    drawing.polygon(((WIDTH - 25, 22), (WIDTH - 29, 34), (WIDTH - 21, 34)), fill=(203, 186, 139))
    return images, geometry


def board_icon(glyph: str) -> Image.Image:
    icon = Image.new("RGBA", (28, 28))
    draw = ImageDraw.Draw(icon)
    ink, paper, brass = "#171e20", "#ded0a6", "#dfb272"
    if glyph in ("trust", "support", "boycott", "resolution"):
        draw.polygon([(3, 3), (18, 3), (24, 8), (24, 24), (3, 24)], fill=paper, outline=ink, width=2)
        draw.line([(5, 22), (5, 5), (17, 5)], fill="#f4e6ba", width=2)
        draw.line((8, 9, 18, 9), fill="#77664c", width=2)
        if glyph in ("trust", "resolution"):
            draw.polygon([(15, 17), (24, 17), (24, 27), (20, 24), (15, 27)], fill="#843b30", outline=ink)
            draw.ellipse((13, 11, 26, 24), fill="#9a4533", outline=ink, width=2)
            draw.ellipse((16, 14, 23, 21), outline="#e99368", width=2)
        else:
            strokes = [[(8, 15), (13, 20), (23, 11)]] if glyph == "support" else [[(8, 11), (21, 21)], [(21, 11), (8, 21)]]
            for stroke in strokes:
                draw.line(stroke, fill=ink, width=6, joint="curve")
            for stroke in strokes:
                draw.line(stroke, fill="#a4d89d" if glyph == "support" else "#ee8166", width=3, joint="curve")
    elif glyph == "slot":
        draw.rounded_rectangle((2, 15, 19, 26), radius=3, fill="#54777d", outline=ink, width=2)
        draw.rectangle((3, 14, 19, 17), fill="#a8c1bf", outline=ink)
        draw.polygon([(10, 20), (14, 8), (25, 1), (23, 11), (17, 16)], fill=paper, outline=ink)
        draw.line((11, 19, 22, 6), fill="#97794c", width=2)
    elif glyph == "committees":
        hook = [(24, 4), (18, 10), (16, 19), (12, 24), (7, 24), (3, 20), (4, 16), (7, 15)]
        draw.line(hook, fill=ink, width=8, joint="curve")
        draw.line(hook, fill="#b9ced1", width=4, joint="curve")
        draw.line((18, 10, 24, 4), fill=brass, width=5)
    elif glyph == "officers":
        draw.polygon([(1, 12), (5, 7), (13, 4), (23, 7), (27, 12), (22, 17), (5, 17)], fill="#dddccc", outline=ink, width=2)
        draw.polygon([(6, 15), (23, 15), (26, 20), (21, 23), (9, 23), (4, 20)], fill="#415f6c", outline=ink, width=2)
        draw.ellipse((12, 8, 16, 12), outline="#745839", width=2)
        draw.line((14, 12, 14, 19), fill=brass, width=2)
        draw.arc((8, 11, 20, 20), 7, 173, fill=brass, width=2)
    elif glyph == "waiting":
        draw.polygon([(5, 4), (22, 4), (20, 11), (16, 14), (20, 17), (22, 24), (5, 24), (8, 17), (12, 14), (8, 11)], fill="#6c5138", outline=ink, width=2)
        draw.polygon([(9, 7), (19, 7), (14, 13)], fill="#f2ca85")
        draw.polygon([(8, 22), (20, 22), (14, 17)], fill="#d9a052")
        for height in (3, 23):
            draw.rectangle((5, height, 22, height + 2), fill=brass, outline=ink)
    elif glyph == "countdown":
        draw.ellipse((2, 3, 24, 25), fill="#55482f", outline=ink, width=2)
        draw.ellipse((4, 5, 22, 23), outline=brass, width=2)
        draw.line([(12, 8), (12, 14), (16, 16)], fill="#f1dfb0", width=2)
        draw.rectangle((19, 9, 25, 24), fill=ink)
        draw.rectangle((21, 10, 24, 17), fill="#ffc665")
        draw.rectangle((21, 20, 24, 23), fill="#ffc665")
    else:
        raise ValueError(f"Unknown board icon: {glyph}")
    return icon


def board_texticons() -> dict[str, Image.Image]:
    images = {}
    for prefix, glyph in (("board", "trust"), ("board", "slot"), ("judas", "committees"), ("judas", "officers")):
        images[f"{prefix}_{glyph}_texticon.png"] = board_icon(glyph).resize((20, 20), Image.Resampling.LANCZOS)
    strip = Image.new("RGBA", (80, 20))
    for index, glyph in enumerate(("support", "waiting", "countdown", "boycott")):
        strip.paste(board_icon(glyph).resize((20, 20), Image.Resampling.LANCZOS), (20 * index, 0))
    images["board_stance_texticon.png"] = strip
    return images


def ui_images() -> dict[str, Image.Image]:
    images = {}
    for name, fill, edge in (("panel.png", (23, 30, 32), (100, 94, 73)),
                            ("row.png", (29, 38, 39), (64, 77, 75))):
        tile = Image.new("RGBA", (64, 64), (*fill, 255))
        draw = ImageDraw.Draw(tile)
        draw.rectangle((0, 0, 63, 63), outline=(*edge, 255))
        draw.line((2, 2, 61, 2), fill=(72, 81, 76))
        images[name] = tile
    marker = Image.new("RGBA", (32, 32))
    draw = ImageDraw.Draw(marker)
    draw.ellipse((1, 1, 30, 30), fill=(19, 30, 32), outline=(219, 187, 121), width=2)
    draw.ellipse((5, 5, 26, 26), outline=(70, 104, 101))
    images["marker.png"] = marker
    for group in ("nam", "oil", "dist", "garr", "trade"):
        icon = Image.new("RGBA", (28, 28))
        draw = ImageDraw.Draw(icon)
        colour = (202, 181, 128, 255)
        if group == "nam":
            draw.rectangle((6, 4, 21, 23), outline=colour, width=2)
            draw.line((10, 9, 18, 9), fill=colour, width=2)
            draw.ellipse((11, 13, 18, 20), outline=colour, width=2)
        elif group == "oil":
            draw.polygon(((14, 3), (6, 16), (7, 22), (14, 25), (21, 22), (22, 16)), fill=colour)
            draw.line((11, 15, 10, 19, 13, 21), fill=(38, 59, 58), width=2)
        elif group == "dist":
            for x, y in ((4, 4), (16, 4), (4, 16), (16, 16)):
                draw.rectangle((x, y, x + 8, y + 8), outline=colour, width=2)
        elif group == "garr":
            draw.polygon(((5, 4), (23, 4), (22, 17), (14, 25), (6, 17)), outline=colour, width=2)
            draw.line((14, 8, 14, 19), fill=colour, width=2)
            draw.line((9, 12, 19, 12), fill=colour, width=2)
        else:
            draw.line((14, 7, 14, 24), fill=colour, width=2)
            draw.ellipse((11, 2, 17, 8), outline=colour, width=2)
            draw.arc((4, 7, 24, 26), 0, 180, fill=colour, width=2)
            draw.line((4, 14, 4, 19), fill=colour, width=2)
            draw.line((24, 14, 24, 19), fill=colour, width=2)
        images[f"support_{group}.png"] = icon
        images[f"texticon_{group}.png"] = icon.resize((20, 20), Image.Resampling.LANCZOS)
    with Image.open(ROOT / "gfx/texticons/adiscord/custom/STP_hw_underground.png") as newspaper:
        images["weber_underground_texticon.png"] = newspaper.resize((20, 20), Image.Resampling.LANCZOS)
    with Image.open(ROOT / "tools/assets/source/focus_icons/NAM/metropolitan_quota_stamp.png") as stamp:
        images["seal_discipline_texticon.png"] = stamp.resize((20, 20), Image.Resampling.LANCZOS)
    focus_art = Path("tools/assets/source/focus_icons")
    for name, art, size in (
        ("foreign_capital", focus_art / "VAL/industrial_budget_banknote_bundles.png", 20),
        ("corporate_influence", Path("gfx/interface/state_modifiers/adiscord/corporate_board.png"), 20),
        ("consolidation", Path("gfx/interface/ideas/NAM/idea_NAM_consolidation_dynamic.png"), 20),
        ("pillar_loyalty", focus_art / "NAM/neutral_basin_diplomatic_handshake.png", 20),
        ("board_votes", focus_art / "NAM/district_assemblies_ballot_box.png", 20),
        ("field_condition", focus_art / "NAM/oil_score_industrial_meter.png", 20),
        ("field_capacity", focus_art / "NAM/quiet_wells_pumpjack.png", 20),
        ("oil_score", focus_art / "NAM/metropolitan_quota_oil_drums_v3.png", 20),
        ("war_cost", Path("gfx/interface/ideas/STP/idea_STP_wartime_strain.png"), 20),
        ("return_readiness", focus_art / "NAM/general_staff_plan_map_board.png", 16),
    ):
        with Image.open(ROOT / art) as source:
            icon = source.convert("RGBA")
        icon = icon.crop(icon.getchannel("A").point(lambda alpha: 255 if alpha >= 14 else 0).getbbox())
        icon.thumbnail((size, size), Image.Resampling.LANCZOS)
        tile = Image.new("RGBA", (size, size))
        tile.alpha_composite(icon, ((size - icon.width) // 2, (size - icon.height) // 2))
        images[f"{name}_texticon.png"] = tile
    images.update(board_texticons())
    return images


def gui_block(geometry: dict[int, dict]) -> str:
    lines = []
    for state in STATES:
        for frame, status in enumerate(("held", "occupied", "lost", "selected"), 1):
            lines.extend(("\t\ticonType = {", f'\t\t\tname = "NAM_bw_map_{state}_{status}"',
                          "\t\t\tposition = { x = 12 y = 66 }",
                          f'\t\t\tquadTextureSprite = "GFX_NAM_bw_state_{state}"',
                          f"\t\t\tframe = {frame}", "\t\t}", ""))
    for number, state in enumerate(STATES, 1):
        x, y = geometry[state]["anchor"]
        lines.extend(("\t\tbuttonType = {", f'\t\t\tname = "NAM_bw_select_{state}"',
                      f"\t\t\tposition = {{ x = {x - 4} y = {y + 50} }}",
                      '\t\t\tquadTextureSprite = "GFX_NAM_bw_marker"',
                      f'\t\t\tbuttonText = "{number:02d}"', '\t\t\tbuttonFont = "hoi_16mbs"',
                      "\t\t\tclicksound = click_default", f'\t\t\tpdx_tooltip = "NAM_bw_map_{state}_tt"',
                      "\t\t}", ""))
    return "\n".join(lines).rstrip()


def gfx_block(images: dict[str, Image.Image]) -> str:
    lines = []
    for filename in images:
        name = Path(filename).stem
        if name in ("panel", "row"):
            lines.extend(("\tcorneredTileSpriteType = {", f'\t\tname = "GFX_NAM_bw_{name}"',
                          "\t\tsize = { x = 64 y = 64 }", f'\t\ttextureFile = "{(OUT / filename).as_posix()}"',
                          "\t\tborderSize = { x = 3 y = 3 }", "\t\ttilingCenter = yes", "\t}", ""))
        else:
            if name.startswith("texticon_"):
                sprite_name = f"GFX_NAM_support_{name.removeprefix('texticon_')}_texticon"
            elif name.endswith("_texticon"):
                sprite_name = f"GFX_NAM_{name}"
            else:
                sprite_name = f"GFX_NAM_bw_{name}"
            lines.extend(("\tspriteType = {", f'\t\tname = "{sprite_name}"',
                          f'\t\ttexturefile = "{(OUT / filename).as_posix()}"',
                          f'\t\tnoOfFrames = {4 if name.startswith("state_") or name == "board_stance_texticon" else 1}'))
            if name == "marker":
                lines.append('\t\teffectFile = "gfx/FX/buttonstate.lua"')
            if sprite_name.endswith("_texticon"):
                lines.append("\t\tlegacy_lazy_load = no")
            lines.extend(("\t}", ""))
    return "\n".join(lines).rstrip()


def replace_generated(path: Path, content: str, indent: str) -> bytes:
    source = (ROOT / path).read_text(encoding="utf-8")
    pattern = rf"(?m)^[\t ]*{BEGIN}.*?^[\t ]*{END}"
    replacement = f"{indent}{BEGIN}\n{content}\n{indent}{END}"
    updated, count = re.subn(pattern, lambda _: replacement, source, flags=re.S)
    if count != 1:
        raise ValueError(f"Expected one generated map section in {path}")
    return updated.encode("utf-8")


def summary_widgets() -> str:
    rows = (
        ("summary_title", 12, 8, 412, 22, "hoi_18mbs"),
        ("export_labels", 12, 34, 188, 36, "hoi_16mbs"),
        ("summary_compact", 212, 34, 212, 36, "hoi_16mbs"),
        ("island_title", 12, 76, 412, 22, "hoi_18mbs"),
        ("island_labels", 12, 101, 188, 55, "hoi_16mbs"),
        ("island_values", 212, 101, 212, 55, "hoi_16mbs"),
    )
    widgets = []
    for key, x, y, width, height, font in rows:
        name = f"NAM_bw_{key}"
        widgets.append(f'''\t\t\tinstantTextBoxType = {{
\t\t\t\tname = "{name}"
\t\t\t\tposition = {{ x = {x} y = {y} }}
\t\t\t\ttext = "{name}"
\t\t\t\tfont = "{font}"
\t\t\t\tmaxWidth = {width}
\t\t\t\tmaxHeight = {height}
\t\t\t\tfixedsize = yes
\t\t\t\tpdx_tooltip = "NAM_bw_export_detail"
\t\t\t}}''')
    return "\n".join(widgets)


def district_cards(source: bytes) -> bytes:
    """Keep the basin cards informational; operations use native map decisions."""
    lines = [
        '\t\tcontainerWindowType = {',
        '\t\t\tname = "NAM_bw_card_background"',
        '\t\t\tposition = { x = 12 y = 358 }',
        '\t\t\tsize = { width = 436 height = 170 }',
        '\t\t\tbackground = {',
        '\t\t\t\tname = "NAM_bw_card_background_texture"',
        '\t\t\t\tquadTextureSprite = "GFX_ADISCORD_decisions_category_desc_bg"',
        '\t\t\t}',
        '\t\t}',
    ]
    for number, state in enumerate(STATES, 1):
        for part, y, font, height in (("title", 366, "hoi_18mbs", 24),
                                      ("body", 393, "hoi_16mbs", 126)):
            name = f"NAM_bw_card_{state}_{part}"
            text = f"{number:02}   [{state}.GetName]" if part == "title" else name
            lines.extend((
                '\t\tinstantTextBoxType = {',
                f'\t\t\tname = "{name}"',
                f'\t\t\tposition = {{ x = 24 y = {y} }}',
                f'\t\t\ttext = "{text}"',
                f'\t\t\tfont = "{font}"',
                '\t\t\tmaxWidth = 412',
                f'\t\t\tmaxHeight = {height}',
                '\t\t\tfixedsize = yes',
            ))
            if part == "body":
                lines.append(f'\t\t\tpdx_tooltip = "NAM_bw_map_{state}_tt"')
            lines.append('\t\t}')
    text = source.decode("utf-8")
    pattern = (r'\t\tcontainerWindowType = \{\n\t\t\tname = "NAM_bw_card_background".*?'
               r'(?=\t\tcontainerWindowType = \{\n\t\t\tname = "NAM_bw_summary")')
    text, count = re.subn(pattern, lambda _: "\n".join(lines) + "\n", text, flags=re.S)
    if count != 1:
        raise ValueError("Expected one basin district-card section")
    text = re.sub(r'(name = "ADISCORD_NAM_basin_window"\n\t\tposition = [^\n]+\n'
                  r'\t\tsize = \{ width = 460 height = )\d+', r'\g<1>708', text)
    text = re.sub(r'(name = "NAM_bw_summary"\n\t\t\tposition = \{ x = 12 y = )\d+',
                  r'\g<1>536', text)
    summary_pattern = (r'\t\t\tinstantTextBoxType = \{\n\t\t\t\tname = "NAM_bw_summary_title".*?'
                       r'(?=\n\t\t\}\n\t\})')
    text, count = re.subn(summary_pattern, lambda _: summary_widgets(), text, flags=re.S)
    if count != 1:
        raise ValueError("Expected one export and islands summary")
    text = text.replace(
        "# Map selection changes presentation only; actions dispatch the original targeted decisions.",
        "# Map selection changes presentation only; operations use native map decisions.")
    return text.encode("utf-8")


def camp_dossiers(source: bytes) -> bytes:
    cards = []
    for camp, character, x in (("weber", "Yaroslav_Weber", 4), ("karamyshev", "Rostislav_Karamyshev", 233)):
        key = f"NAM_judas_{camp}"
        cards.append(f'''		containerWindowType = {{
			name = "{key}_card"
			position = {{ x = {x} y = {2 + CATEGORY_PICTURE_GAP} }}
			size = {{ width = 223 height = 148 }}
			background = {{
				name = "{key}_background"
				quadTextureSprite = "GFX_ADISCORD_decisions_category_desc_bg"
			}}
			iconType = {{
				name = "{key}_portrait"
				position = {{ x = 8 y = 7 }}
				spriteType = "GFX_portrait_NAM_{character}"
				scale = 0.25
				pdx_tooltip = "{key}_details"
			}}
			instantTextBoxType = {{
				name = "{key}_heading"
				position = {{ x = 55 y = 9 }}
				text = "{key}_heading"
				font = "hoi_16mbs"
				maxWidth = 160
				maxHeight = 48
				fixedsize = yes
				pdx_tooltip = "{key}_details"
			}}
			instantTextBoxType = {{
				name = "{key}_summary"
				position = {{ x = 10 y = 66 }}
				text = "{key}_summary"
				font = "hoi_16mbs"
				maxWidth = 203
				maxHeight = 76
				fixedsize = yes
				pdx_tooltip = "{key}_details"
			}}
		}}''')

    start = "\t# BEGIN GENERATED NAM CAMP DOSSIERS"
    end = "\t# END GENERATED NAM CAMP DOSSIERS"
    panel = (start + '\n\tcontainerWindowType = {\n\t\tname = "ADISCORD_NAM_camps_window"\n'
             '\t\tposition = { x = 0 y = 0 }\n'
             f'\t\tsize = {{ width = 460 height = {152 + CATEGORY_PICTURE_GAP} }}\n'
             + "\n\n".join(cards) + "\n\t}\n" + end + "\n\n")
    anchor = '\tcontainerWindowType = {\n\t\tname = "ADISCORD_NAM_board_window"'
    pattern = rf"(?:{re.escape(start)}.*?{re.escape(end)}\n\n)?(?={re.escape(anchor)})"
    text, count = re.subn(pattern, lambda _: panel, source.decode("utf-8"), count=1, flags=re.S)
    if count != 1:
        raise ValueError("Expected the corporate board window")
    return text.encode("utf-8")


def board_picture_gap(source: bytes) -> bytes:
    text = source.decode("utf-8")
    start = text.index('\tcontainerWindowType = {\n\t\tname = "ADISCORD_NAM_board_window"')
    end = text.index("\n\t}", start)
    board = text[start:end]
    # Direct children include the pyramid, its overlays and the transparent seat buttons.
    positions = re.compile(r"^(\t{3}position = \{ x = -?\d+ y = )(-?\d+)", re.M)
    offset = CATEGORY_PICTURE_GAP - min(int(match[2]) for match in positions.finditer(board))
    if offset:
        def shift(match):
            return match[1] + str(int(match[2]) + offset)

        board = positions.sub(shift, board)
        board, count = re.subn(r"^(\t{2}size = \{ width = \d+ height = )(\d+)", shift, board, flags=re.M)
        if count != 1:
            raise ValueError("Expected one corporate board window size")
    return (text[:start] + board + text[end:]).encode("utf-8")


def report_card(name, x, y, width, height, fields):
    lines = [
        "\t\tcontainerWindowType = {",
        f'\t\t\tname = "{name}"',
        f"\t\t\tposition = {{ x = {x} y = {y} }}",
        f"\t\t\tsize = {{ width = {width} height = {height} }}",
        "\t\t\tbackground = {",
        f'\t\t\t\tname = "{name}_background"',
        '\t\t\t\tquadTextureSprite = "GFX_ADISCORD_decisions_category_desc_bg"',
        "\t\t\t}",
    ]
    for key, left, top, span, depth, tip in fields:
        lines.extend((
            "\t\t\tinstantTextBoxType = {",
            f'\t\t\t\tname = "{key}"',
            f"\t\t\t\tposition = {{ x = {left} y = {top} }}",
            f'\t\t\t\ttext = "{key}"',
            '\t\t\t\tfont = "hoi_16mbs"',
            f"\t\t\t\tmaxWidth = {span}",
            f"\t\t\t\tmaxHeight = {depth}",
            "\t\t\t\tfixedsize = yes",
            f'\t\t\t\tpdx_tooltip = "{tip}"',
            "\t\t\t}",
        ))
    return "\n".join([*lines, "\t\t}"])


def mainland_reports(source: bytes) -> bytes:
    text = source.decode("utf-8")
    # The course needs a full line for the longest party majority in either language.
    for tile, left, width in (("phase", 12, 108), ("underground", 128, 100), ("ladder", 236, 212)):
        pattern = rf'(name = "NAM_bw_{tile}"\n\s+position = \{{ x = )\d+( y = 4 \}}\n\s+size = \{{ width = )\d+'
        text, count = re.subn(pattern, rf"\g<1>{left}\g<2>{width}", text)
        if count != 1:
            raise ValueError(f"Expected basin header tile {tile}")
        for field, top, height in (("label", 6, 18), ("value", 29, 22)):
            pattern = (rf'(name = "NAM_bw_{tile}_{field}"\n\s+position = \{{ x = 8 y = )\d+'
                       r'( \}\n\s+text = "[^"]*"\n\s+font = "[^"]*"\n\s+maxWidth = )\d+(\n\s+maxHeight = )\d+')
            text, count = re.subn(pattern, rf"\g<1>{top}\g<2>{width - 16}\g<3>{height}", text)
            if count != 1:
                raise ValueError(f"Expected {field} in basin header tile {tile}")

    calendar = [("NAM_calendar_heading", 10, 7, 430, 19, "NAM_calendar_rules")]
    for i, measure in enumerate(("desk", "azhar", "claims", "dossier", "protocol")):
        y = 32 + i * 24
        key = f"NAM_calendar_{measure}"
        calendar.extend((
            (key, 10, y, 203, 21, "NAM_calendar_rules"),
            (key + "_days", 218, y, 65, 21, "NAM_calendar_rules"),
            (key + "_status", 289, y, 150, 21, "NAM_calendar_rules"),
        ))
    calendar.append(("NAM_calendar_price", 10, 158, 428, 38, "NAM_calendar_rules"))
    reports = {
        "calendar": (206, [report_card("NAM_calendar_table", 4, 2, 452, 200, calendar)]),
        "network": (172, [
            report_card("NAM_network_growth", 4, 2, 223, 166, [
                ("NAM_network_growth_title", 10, 7, 203, 20, "NAM_network_growth_rules"),
                ("NAM_network_factors", 10, 33, 203, 129, "NAM_network_growth_rules"),
            ]),
            report_card("NAM_network_security", 233, 2, 223, 166, [
                ("NAM_network_risk_title", 10, 7, 203, 20, "NAM_network_risk_rules"),
                ("NAM_network_risk", 10, 31, 203, 48, "NAM_network_risk_rules"),
                ("NAM_network_guard_title", 10, 77, 203, 20, "NAM_network_risk_rules"),
                ("NAM_network_guards", 10, 101, 203, 59, "NAM_network_risk_rules"),
            ]),
        ]),
        "reserve": (240, [
            report_card("NAM_reserve_ledger", 4, 2, 223, 137, [
                ("NAM_reserve_title", 10, 7, 203, 20, "NAM_reserve_rules"),
                ("NAM_reserve_units", 10, 32, 203, 100, "NAM_reserve_rules"),
            ]),
            report_card("NAM_reserve_works", 233, 2, 223, 137, [
                ("NAM_reserve_works_title", 10, 7, 203, 20, "NAM_reserve_defence_rules"),
                ("NAM_mobilisation_active_desc", 10, 32, 203, 100, "NAM_reserve_defence_rules"),
            ]),
            report_card("NAM_reserve_districts", 4, 143, 452, 93, [
                ("NAM_reserve_hold_title", 10, 7, 430, 20, "NAM_hold_field_context_tt"),
                ("NAM_reserve_hold_names", 10, 30, 202, 57, "NAM_hold_field_context_tt"),
                ("NAM_reserve_hold_orders", 219, 30, 222, 57, "NAM_hold_field_context_tt"),
            ]),
        ]),
    }
    windows = []
    for name, (height, cards) in reports.items():
        windows.append("\n".join([
            "\tcontainerWindowType = {", f'\t\tname = "ADISCORD_NAM_{name}_window"',
            "\t\tposition = { x = 0 y = 0 }", f"\t\tsize = {{ width = 460 height = {height} }}",
            "\n\n".join(cards), "\t}",
        ]))
    begin = "\t# BEGIN GENERATED NAM MAINLAND REPORTS"
    end = "\t# END GENERATED NAM MAINLAND REPORTS"
    anchor = "\t# BEGIN GENERATED NAM CAMP DOSSIERS"
    region = begin + "\n" + "\n\n".join(windows) + "\n" + end + "\n\n"
    pattern = rf"(?:{re.escape(begin)}.*?{re.escape(end)}\n\n)?(?={re.escape(anchor)})"
    text, count = re.subn(pattern, lambda _: region, text, count=1, flags=re.S)
    if count != 1:
        raise ValueError("Expected NAM dossier windows")
    return text.encode("utf-8")


def build_outputs() -> tuple[dict[Path, bytes], dict[int, dict]]:
    images, geometry = map_images()
    images.update(ui_images())
    outputs = {}
    for filename, image in images.items():
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        outputs[OUT / filename] = buffer.getvalue()
    basin_gui = district_cards(replace_generated(GUI, gui_block(geometry), "\t\t"))
    outputs[GUI] = mainland_reports(camp_dossiers(board_picture_gap(basin_gui)))
    outputs[GFX] = replace_generated(GFX, gfx_block(images), "\t")
    return outputs, geometry


def check_outputs(outputs: dict[Path, bytes]) -> list[str]:
    return [path.as_posix() for path, expected in outputs.items()
            if not (ROOT / path).is_file() or (ROOT / path).read_bytes() != expected]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check generated assets (default)")
    mode.add_argument("--apply", action="store_true", help="write changed assets and map bindings")
    args = parser.parse_args()
    outputs, _ = build_outputs()
    changed = check_outputs(outputs)
    if args.apply:
        for relative in changed:
            path = ROOT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(outputs[Path(relative)])
        print(f"NAM basin assets written: {len(changed)}")
    else:
        for relative in changed:
            print(f"Different or missing: {relative}")
    print(f"NAM basin assets checked: {len(outputs)}; differences: {len(check_outputs(outputs))}")
    return int(bool(check_outputs(outputs)))


if __name__ == "__main__":
    raise SystemExit(main())
