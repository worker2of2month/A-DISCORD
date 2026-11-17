#!/usr/bin/env python3
"""Build original, small-format-readable flags for Vorkerland successor states."""

from __future__ import annotations

import argparse
import math
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps
from tools.lib.paths import repository_root


ROOT = repository_root()
FLAG_ROOT = ROOT / "gfx" / "flags"
SOURCE_ROOT = ROOT / "tools/assets/source/vorkerland_flags"
CANVAS = (656, 416)


def points(
    cx: int, cy: int, outer: int, inner: int, count: int, offset: float = -math.pi / 2
):
    result = []
    for index in range(count * 2):
        radius = outer if index % 2 == 0 else inner
        angle = offset + index * math.pi / count
        result.append(
            (cx + round(math.cos(angle) * radius), cy + round(math.sin(angle) * radius))
        )
    return result


def ring(
    draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str, width: int
) -> None:
    draw.ellipse(box, outline=color, width=width)


def eba() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#17372f")
    draw = ImageDraw.Draw(image)
    cream, copper = "#ead39a", "#b86b35"
    draw.rectangle((0, 0, 655, 415), outline=cream, width=20)
    draw.rectangle((0, 300, 655, 415), fill="#112723")
    draw.line((70, 315, 586, 315), fill=copper, width=18)
    draw.arc((120, 100, 536, 430), 180, 360, fill=cream, width=28)
    for x in (170, 260, 350, 440, 530):
        draw.rectangle((x - 12, 250, x + 12, 350), fill=cream)
    draw.polygon(((328, 75), (355, 132), (328, 120), (301, 132)), fill=copper)
    return image


def tgd() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#263744")
    draw = ImageDraw.Draw(image)
    pale, cyan = "#d8e0d9", "#4fa4a3"
    draw.rectangle((0, 0, 655, 415), outline="#182630", width=22)
    draw.polygon(points(328, 207, 142, 108, 12), fill=pale)
    draw.ellipse((238, 117, 418, 297), fill="#263744")
    ring(draw, (265, 144, 391, 270), cyan, 18)
    draw.rectangle((165, 255, 491, 340), fill="#182630", outline=pale, width=14)
    for x, height in ((205, 58), (270, 82), (335, 48), (400, 95), (465, 65)):
        draw.rectangle((x - 16, 325 - height, x + 16, 325), fill=cyan)
    return image


def ibl() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#314630")
    draw = ImageDraw.Draw(image)
    bone, gold = "#e2d4a7", "#b58b42"
    draw.polygon(((0, 70), (656, 0), (656, 82), (0, 152)), fill=gold)
    draw.polygon(((0, 264), (656, 334), (656, 416), (0, 346)), fill=gold)
    draw.polygon(
        ((328, 68), (470, 120), (446, 300), (328, 365), (210, 300), (186, 120)),
        fill=bone,
    )
    draw.polygon(
        ((328, 100), (430, 138), (412, 278), (328, 324), (244, 278), (226, 138)),
        fill="#314630",
    )
    draw.line((267, 237, 389, 237), fill=gold, width=22)
    draw.line((287, 190, 369, 190), fill=gold, width=18)
    return image


def wtd() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#243f4b")
    draw = ImageDraw.Draw(image)
    pale, copper, deep = "#dde4d6", "#d18445", "#162b33"
    draw.rectangle((0, 0, 655, 415), outline=deep, width=24)
    draw.polygon(
        ((328, 58), (455, 132), (455, 284), (328, 358), (201, 284), (201, 132)),
        fill=pale,
    )
    draw.polygon(
        ((328, 94), (420, 147), (420, 269), (328, 322), (236, 269), (236, 147)),
        fill=deep,
    )
    ring(draw, (276, 156, 380, 260), copper, 18)
    draw.line((0, 208, 205, 208), fill=copper, width=18)
    draw.line((451, 208, 656, 208), fill=copper, width=18)
    draw.line((328, 0, 328, 96), fill=copper, width=18)
    draw.line((328, 320, 328, 416), fill=copper, width=18)
    return image


def slf() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#1a1b18")
    draw = ImageDraw.Draw(image)
    gold, orange = "#f0c65a", "#ca691f"
    draw.rectangle((0, 320, 655, 415), fill=gold)
    draw.pieslice((198, 118, 458, 378), 180, 360, fill=orange)
    for angle in range(200, 341, 20):
        rad = math.radians(angle)
        draw.line(
            (328, 248, 328 + math.cos(rad) * 225, 248 + math.sin(rad) * 225),
            fill=gold,
            width=15,
        )
    draw.rectangle((0, 248, 655, 282), fill="#1a1b18")
    draw.polygon(((260, 320), (328, 230), (396, 320)), fill="#1a1b18")
    return image


def pwr() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#6b2838")
    draw = ImageDraw.Draw(image)
    cream, wheat = "#f1dfb6", "#d4a34b"
    draw.rectangle((0, 150, 655, 266), fill=cream)
    ring(draw, (222, 70, 434, 346), wheat, 18)
    draw.ellipse((262, 106, 394, 310), fill="#6b2838")
    draw.line((328, 122, 328, 292), fill=cream, width=15)
    for y, side in ((155, 1), (190, -1), (225, 1), (260, -1)):
        draw.line((328, y, 328 + side * 70, y - 32), fill=wheat, width=14)
    return image


def rom() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#315267")
    draw = ImageDraw.Draw(image)
    white, rose = "#e9ede4", "#b76f82"
    draw.rectangle((0, 290, 655, 415), fill="#183748")
    for y in (310, 352, 394):
        draw.arc((-40, y - 35, 250, y + 35), 190, 350, fill=rose, width=14)
        draw.arc((200, y - 35, 490, y + 35), 190, 350, fill=rose, width=14)
        draw.arc((440, y - 35, 730, y + 35), 190, 350, fill=rose, width=14)
    draw.polygon(
        (
            (170, 225),
            (278, 130),
            (332, 190),
            (395, 108),
            (486, 218),
            (396, 183),
            (332, 248),
            (270, 188),
        ),
        fill=white,
    )
    draw.ellipse((305, 176, 350, 221), fill=rose)
    return image


def tru() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#61302a")
    draw = ImageDraw.Draw(image)
    gold, dark = "#e4b552", "#30251f"
    draw.polygon(points(328, 180, 146, 105, 16), fill=gold)
    draw.ellipse((240, 92, 416, 268), fill=dark)
    draw.ellipse((266, 118, 390, 242), fill=gold)
    draw.polygon(
        (
            (0, 416),
            (0, 345),
            (130, 260),
            (235, 335),
            (350, 245),
            (480, 345),
            (656, 275),
            (656, 416),
        ),
        fill=dark,
    )
    draw.line((0, 350, 656, 350), fill=gold, width=18)
    return image


def vla() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#6c2e2e")
    draw = ImageDraw.Draw(image)
    stone, dark = "#e7dfce", "#332825"
    draw.polygon(
        ((0, 0), (160, 0), (656, 300), (656, 416), (520, 416), (0, 105)), fill=dark
    )
    draw.rectangle((272, 110, 384, 350), fill=stone)
    draw.polygon(
        (
            (246, 126),
            (410, 126),
            (380, 76),
            (350, 112),
            (328, 65),
            (303, 112),
            (275, 76),
        ),
        fill=stone,
    )
    draw.rectangle((307, 258, 349, 350), fill=dark)
    draw.line((215, 350, 441, 350), fill=stone, width=24)
    return image


def zao() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#174765")
    draw = ImageDraw.Draw(image)
    white, light = "#e9e4cf", "#e3a844"
    for end in ((60, 40), (170, 0), (328, 0), (486, 0), (596, 40)):
        draw.line((328, 185, *end), fill=light, width=18)
    draw.rectangle((0, 295, 655, 415), fill="#102f45")
    draw.polygon(((270, 330), (294, 128), (362, 128), (386, 330)), fill=white)
    draw.rectangle((270, 122, 386, 162), fill="#b84535")
    draw.ellipse((301, 76, 355, 130), fill=light)
    draw.line((0, 350, 656, 350), fill=light, width=13)
    return image


def slf_republic() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#1f6b5f")
    draw = ImageDraw.Draw(image)
    mint, deep = "#dce8c8", "#144b49"
    draw.rectangle((0, 0, 170, 416), fill=deep)
    draw.polygon(
        (
            (0, 315),
            (155, 250),
            (315, 330),
            (480, 245),
            (656, 310),
            (656, 416),
            (0, 416),
        ),
        fill=mint,
    )
    draw.polygon(
        ((355, 58), (443, 179), (405, 285), (328, 315), (256, 260), (265, 170)),
        fill=mint,
    )
    draw.line((300, 245, 405, 128), fill=deep, width=17)
    draw.line((331, 211, 280, 186), fill=deep, width=13)
    draw.line((365, 174, 409, 184), fill=deep, width=13)
    return image


def csl() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#382b42")
    draw = ImageDraw.Draw(image)
    cream, orange = "#e6d4ad", "#b86135"
    draw.rectangle((0, 0, 655, 415), outline=orange, width=22)
    draw.rectangle((135, 78, 521, 350), fill="#211c27", outline=cream, width=18)
    for x in (185, 255, 401, 471):
        draw.rectangle((x - 22, 128, x + 22, 350), fill=cream)
        draw.polygon(((x - 35, 128), (x, 76), (x + 35, 128)), fill=orange)
    draw.arc((258, 168, 398, 390), 180, 360, fill=orange, width=28)
    draw.rectangle((285, 255, 371, 350), fill="#382b42")
    return image


def confederal_district(kind: str) -> Image.Image:
    """District banners retain the federal colours and the existing fist seal."""
    orange, gold, red, blue = "#ff9100", "#efc75d", "#b8261c", "#086abb"
    image = Image.new("RGB", CANVAS, orange)
    draw = ImageDraw.Draw(image)
    if kind == "garrison":
        draw.rectangle((0, 0, 655, 415), fill=red)
        draw.rectangle((0, 164, 655, 252), fill=gold)
        draw.polygon(
            ((70, 0), (210, 0), (330, 208), (210, 416), (70, 416), (190, 208)),
            fill=orange,
        )
        centre = (328, 208)
    elif kind == "river":
        draw.rectangle((0, 0, 655, 415), fill=blue)
        draw.rectangle((0, 136, 655, 280), fill=gold)
        draw.rectangle((0, 161, 655, 255), fill=orange)
        centre = (196, 208)
    else:
        draw.rectangle((0, 0, 655, 137), fill=red)
        draw.rectangle((0, 138, 655, 277), fill="#ffffff")
        draw.rectangle((0, 278, 655, 415), fill=orange)
        centre = (328, 208)
    cx, cy = centre
    draw.ellipse((cx - 100, cy - 100, cx + 100, cy + 100), fill=gold)
    draw.ellipse((cx - 82, cy - 82, cx + 82, cy + 82), fill="#101010")
    # Use the canonical federation seal; it is a supplied asset, not a new logo.
    with Image.open(FLAG_ROOT / "WRK.tga") as source:
        seal = (
            source.convert("RGB")
            .crop((18, 17, 35, 37))
            .resize((100, 118), Image.Resampling.LANCZOS)
        )
    image.paste(seal, (cx - 50, cy - 59))
    return image


def veyran_crown(source: Image.Image) -> Image.Image:
    image = Image.new("RGB", CANVAS, "#791e26")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 169, 655, 247), fill="#dcb257")
    draw.rectangle((175, 0, 253, 415), fill="#dcb257")
    draw.ellipse((97, 91, 331, 325), fill="#761c23", outline="#dcb257", width=13)
    eagle = source.convert("RGB").crop((20, 9, 63, 42)).resize((190, 146), Image.Resampling.LANCZOS)
    mask = Image.new("L", eagle.size)
    ImageDraw.Draw(mask).ellipse((0, 0, 189, 145), fill=255)
    image.paste(eagle, (119, 135), mask)
    return image


BUILDERS = {
    "EGC": lambda: confederal_district("garrison"),
    "RIV": lambda: confederal_district("river"),
    "YOR": lambda: confederal_district("republic"),
    "EBA": eba,
    "TGD": tgd,
    "IBL": ibl,
    "WTD": wtd,
    "SLF": slf,
    "PWR_rimat_republic": pwr,
    "ROM_frealor_republic": rom,
    "VLA_volnograd_republic": vla,
    "ZAO_zaozersk_republic": zao,
    "SLF_svetlogorsk_republic": slf_republic,
    "CSL": csl,
}

SUPPLIED_FLAGS = {
    "WRK_vorkerland_world_empire": SOURCE_ROOT / "WRK_vorkerland_world_empire.png",
    "ROM": SOURCE_ROOT / "ROM.png",
    "TRU": SOURCE_ROOT / "TRU.png",
    "IBA": SOURCE_ROOT / "IBA.png",
    "TRU_zolotorevsk_republic": SOURCE_ROOT / "TRU_zolotorevsk_republic.png",
    "WRK_vorkerland_utilitarian_republic": SOURCE_ROOT
    / "WRK_vorkerland_utilitarian_republic.png",
}

SUPPLIED_RUNTIME_FLAGS = {
    "SOL_vorkerland_worker_protectorate": SOURCE_ROOT
    / "SOL_vorkerland_worker_protectorate.png",
}

ARTWORK_FLAGS = {
    "MZR": SOURCE_ROOT.parent / "country_flags/MZR.png",
    "WRK_technocracy": SOURCE_ROOT / "WRK_technocracy.png",
    "RUS_restoration_state": SOURCE_ROOT / "RUS_restoration_state.png",
    "RUS_black_banner_empire": SOURCE_ROOT / "RUS_black_banner_empire.png",
}

# Each postwar design uses the canonical arms of its government.
WEST_VICTORY_FLAGS = {
    "IVN_cw_committee_west_victory": "IVC",
    "IVN_unified_directory_west_victory": "IMD",
    "IVN_unified_communes_west_victory": "IFC",
    "IVN_unified_marches_west_victory": "IAM",
    "WRK_vorkerland_joint_government_west_victory": "WRK_vorkerland_joint_government",
    "VAD_vorkerland_restoration_west_victory": "VAD_vorkerland_restoration",
    "VAD_vorkerland_collegial_staff_west_victory": "VAD",
    "VAD_vorkerland_staff_republic_west_victory": "VAD_vorkerland_restoration",
    "WRK_vorkerland_world_empire_west_victory": "WRK_vorkerland_world_empire",
    "IVN_west_victory": "IVN",
    "IVN_west_victory_chauvinism": "IVN_chauvinism",
    "IVN_west_victory_etatism": "IVN_etatism",
    "WRK_western_eastern_union": "WRK_vorkerland_emergency",
    "WRK_republican_union": "WRK_vorkerland_utilitarian_republic",
    "WRK_forul_technical_union": "WRK_technocracy",
    "WRK_veyran_empire": "WRK_vorkerland_world_empire",
}

WEST_MANDATE_FLAGS = {
    "IVN_cw_committee_west_mandate": ("IVC", "WRK"),
    "IVN_unified_directory_west_mandate": ("IMD", "WRK"),
    "IVN_unified_communes_west_mandate": ("IFC", "WRK"),
    "IVN_unified_marches_west_mandate": ("IAM", "WRK"),
    "WRK_vorkerland_joint_government_west_mandate": ("WRK_vorkerland_joint_government", "IVN"),
    "VAD_vorkerland_restoration_west_mandate": ("VAD_vorkerland_restoration", "IVN"),
    "VAD_vorkerland_collegial_staff_west_mandate": ("VAD", "IVN"),
    "VAD_vorkerland_staff_republic_west_mandate": ("VAD_vorkerland_restoration", "IVN"),
    "WRK_vorkerland_world_empire_west_mandate": ("WRK_vorkerland_world_empire", "IVN"),
    "WRK_vorkerland_emergency_west_mandate": ("WRK_vorkerland_emergency", "IVN"),
    "WRK_vorkerland_utilitarian_republic_west_mandate": ("WRK_vorkerland_utilitarian_republic", "IVN"),
    "WRK_vorkerland_technocracy_west_mandate": ("WRK_technocracy", "IVN"),
    "WRK_west_mandate": ("WRK", "IVN"),
    "IVN_west_mandate": ("IVN", "WRK"),
}
for republic in ("WIT", "IIA", "IBA", "IBL", "PWR", "PSD", "ZAO", "WPA", "WPS", "ROM", "TRU", "PWR_rimat_republic"):
    for patron in ("IVN", "WRK"):
        WEST_MANDATE_FLAGS[f"{republic}_west_{patron}_mandate"] = (republic, patron)


def laurel(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, gold: str,
           sweep: int = 101) -> None:
    for side in (-1, 1):
        branch = []
        for angle in range(8, sweep + 1, 3):
            a = math.radians(angle)
            branch.append((cx + side * radius * math.sin(a), cy + radius * math.cos(a)))
        draw.line(branch, fill=gold, width=7)
        for angle in range(16, sweep, 13):
            a = math.radians(angle)
            x = cx + side * radius * math.sin(a)
            y = cy + radius * math.cos(a)
            for tilt in (-0.62, 0.68):
                dx, dy = side * math.cos(a - tilt), -math.sin(a - tilt)
                draw.polygon(((x, y), (x + 16*dx - 7*dy, y + 16*dy + 7*dx),
                              (x + 35*dx, y + 35*dy),
                              (x + 19*dx + 7*dy, y + 19*dy - 7*dx)), fill=gold)


def union_standard() -> Image.Image:
    black, orange, ink, gold, ivory = "#141619", "#b9561c", "#192a30", "#e3af55", "#f8e6b4"
    cloth = Image.new("RGB", CANVAS, black)
    draw = ImageDraw.Draw(cloth)
    for edge in (0, 656):
        draw.polygon(((edge, 10), (328, 201), (edge, 406)), fill=orange)
        draw.polygon(((edge, 91), (328, 201), (edge, 325)), fill=black)
    for y in (19, 389):
        draw.rectangle((0, y, 655, y+7), fill=gold)
    # A stepped wing on either side carries the wheel across the full standard.
    for side in (-1, 1):
        for left, right, y in ((86, 285, 135), (89, 252, 176), (90, 213, 217)):
            wing = ((left, y+26), (right, y-9), (right-26, y+22), (left, y+55))
            draw.polygon([(328+side*x, h) for x, h in wing], fill=gold)
            draw.line([(328+side*x, h) for x, h in wing[:2]], fill=ivory, width=6)
    draw.ellipse((222, 85, 434, 297), fill=ink, outline=ivory, width=9)
    # Fit the entire original cog and its three-way junction inside the new arms.
    with Image.open(SUPPLIED_FLAGS["WRK_vorkerland_utilitarian_republic"]) as source:
        wheel = ImageOps.fit(source.convert("RGB"), CANVAS).crop((218, 98, 438, 318))
    wheel = wheel.resize((196, 196), Image.Resampling.LANCZOS)
    mask = Image.new("L", wheel.size)
    ImageDraw.Draw(mask).ellipse((0, 0, 195, 195), fill=255)
    cloth.paste(wheel, (230, 93), mask)
    laurel(draw, 328, 209, 132, gold, sweep=63)
    draw.polygon(points(328, 60, 24, 9, 4), fill=ivory)
    draw.polygon(((301, 344), (328, 332), (355, 344), (328, 358)), fill=ivory)
    return cloth


# Charge boxes are in the 82 x 52 national masters. They preserve each local
# device's proportions when mounted on a roundel or a lozenge.
MANDATE_HERALDRY = {
    # field, ground, secondary tincture, charge box, centre x, charge diameter
    "IVN": ("pall", "#115346", "#ede1b9", (21, 0, 65, 50), 358, 255),
    "IVC": ("pile", "#8c2038", "#202934", (39, 0, 79, 51), 328, 248),
    "IMD": ("wings", "#124b42", "#dbc58e", (20, 0, 64, 52), 328, 256),
    "IFC": ("quarters", "#216454", "#e9dbb1", (21, 0, 65, 50), 328, 244),
    "IAM": ("saltire", "#79253c", "#ded0ad", (14, 0, 68, 52), 328, 250),
    "IIA": ("waves", "#103e50", "#448078", (24, 2, 58, 49), 328, 232),
    "IBA": ("eclipse", "#182a4c", "#ccb077", (25, 9, 57, 42), 260, 232),
    "IBL": ("pile", "#344838", "#ac8745", (22, 6, 60, 46), 328, 240),
    "PWR": ("sunrise", "#aa3032", "#e4a43e", (23, 6, 59, 46), 328, 226),
    "PWR_rimat_republic": ("wings", "#632639", "#deca95", (25, 7, 57, 46), 328, 236),
    "PSD": ("pall", "#534358", "#d8c9bb", (14, 10, 45, 42), 365, 220),
    "ZAO": ("sunrise", "#813930", "#c67836", (24, 9, 58, 43), 268, 225),
    "ROM": ("saltire", "#173c58", "#ac383f", (23, 8, 60, 43), 328, 244),
    "TRU": ("quarters", "#583868", "#de943f", (5, 10, 37, 42), 328, 238),
}


def mandate_field(draw: ImageDraw.ImageDraw, kind: str, base: str, accent: str, cx: int) -> None:
    gold = "#e9c578"
    if kind == "pall":
        for color, width in ((gold, 83), (accent, 57)):
            for edge in ((0, -5), (0, 421), (656, 208)):
                draw.line((cx, 208, *edge), fill=color, width=width)
    elif kind == "pile":
        for span, color in ((310, gold), (286, accent)):
            draw.polygon(((cx-span, 0), (cx+span, 0), (cx, 405)), fill=color)
    elif kind == "eclipse":
        draw.polygon(((0, 330), (500, 0), (656, 0), (656, 85), (156, 416), (0, 416)), fill=accent)
        for x in (85, 115, 520, 550):
            draw.line((x-230, 416, x+395, 0), fill=gold, width=9)
    elif kind == "wings":
        for edge, side in ((0, 1), (656, -1)):
            for y, length in ((73, 289), (142, 243), (211, 198)):
                draw.polygon(((edge, y), (edge+side*length, y+79),
                              (edge+side*length, y+116), (edge, y+30)), fill=accent)
    elif kind == "quarters":
        draw.rectangle((0, 0, cx, 207), fill=accent)
        draw.rectangle((cx, 208, 655, 415), fill=accent)
        for x, y in ((cx//2, 103), ((cx+656)//2, 313)):
            draw.polygon(points(x, y, 38, 12, 4), fill=base)
    elif kind == "saltire":
        for color, width in ((gold, 62), (accent, 41)):
            draw.line((-15, -10, 671, 426), fill=color, width=width)
            draw.line((-15, 426, 671, -10), fill=color, width=width)
    elif kind == "waves":
        for y in (300, 354):
            line = [(x, y+11*math.sin(x*math.pi/84)) for x in range(0, 661, 4)]
            draw.line(line, fill=accent if y == 300 else gold, width=18)
        draw.polygon(((0, 0), (656, 0), (cx, 148)), fill=accent)
    elif kind == "sunrise":
        for angle in range(0, 181, 18):
            ray = [(cx, 268)]
            for end in (angle-4, angle+4):
                a = math.radians(end)
                ray.append((cx+750*math.cos(a), 268-750*math.sin(a)))
            draw.polygon(ray, fill=accent)
        draw.rectangle((0, 267, 655, 290), fill=gold)


def western_subject_standard(source: Image.Image, source_id: str) -> Image.Image:
    gold, ivory = "#e9c578", "#f6e6c0"
    if source_id in ("WIT", "WPA", "WPS"):
        # These countries identify themselves by bands and geometric charges.
        fields = {"WIT": ("#192e4b", "#ac3644"), "WPA": ("#29485c", "#8eafb9"),
                  "WPS": ("#233b53", "#c89648")}
        base, accent = fields[source_id]
        cloth = Image.new("RGB", CANVAS, base)
        d = ImageDraw.Draw(cloth)
        if source_id == "WIT":
            d.rectangle((0, 0, 656, 180), fill=ivory)
            d.rectangle((0, 180, 656, 274), fill=accent)
            # The city gate interrupts the original white, red and blue tricolour.
            d.rectangle((202, 140, 454, 302), fill=gold)
            for x in (202, 252, 303, 354, 405):
                d.rectangle((x, 100, x+48-12, 142), fill=gold)
            d.pieslice((274, 173, 382, 297), 180, 360, fill=base)
            d.rectangle((274, 235, 382, 303), fill=base)
            d.line((84, 302, 572, 302), fill=gold, width=9)
        elif source_id == "WPA":
            d.rectangle((0, 170, 655, 246), fill=ivory)
            for x, color in ((169, gold), (319, accent)):
                d.polygon(((x+100, 28), (x+175, 28), (x+46, 208), (x+175, 388),
                           (x+100, 388), (x-32, 208)), fill=base, outline=base, width=14)
                d.polygon(((x+104, 46), (x+149, 46), (x+27, 208), (x+149, 370),
                           (x+104, 370), (x-14, 208)), fill=color)
            d.polygon(points(118, 208, 41, 13, 4), fill=base)
        else:
            for color, width in ((ivory, 158), (accent, 131)):
                d.line((33, 443, 623, -27), fill=color, width=width)
            for x,y in ((186, 318), (328, 208), (470, 98)):
                d.polygon(((x-34,y-23),(x+10,y-38),(x+34,y+23),(x-10,y+38)), fill=base)
            for x,y in ((100, 90), (556, 326)):
                d.polygon(points(x, y, 32, 11, 4), fill=gold)
        return cloth

    kind, base, accent, box, cx, size = MANDATE_HERALDRY[source_id]
    cloth = Image.new("RGB", CANVAS, base)
    d = ImageDraw.Draw(cloth)
    mandate_field(d, kind, base, accent, cx)
    cy = 196 if kind == "waves" else 208
    r = size//2
    # Mask at the edge of the national field, leaving the heraldic charge intact.
    national = source.convert("RGB")
    badge = ImageOps.pad(national.crop(box), (size, size), method=Image.Resampling.LANCZOS,
                         color=national.getpixel((box[0], box[1])))
    mask = Image.new("L", badge.size)
    cut = ImageDraw.Draw(mask)
    last = size - 1
    if source_id in ("IVC", "IMD", "IBL", "IAM"):
        cut.polygon(((0, 0), (last, 0), (last, r), (int(size*.85), int(size*.78)),
                     (r, last), (int(size*.15), int(size*.78)), (0, r)), fill=255)
    elif source_id in ("TRU", "ROM"):
        cut.polygon(((r, 0), (last, r), (r, last), (0, r)), fill=255)
    else:
        cut.ellipse((0, 0, last, last), fill=255)
    border = mask.resize((size+20, size+20), Image.Resampling.LANCZOS)
    cloth.paste(gold, (cx-r-10, cy-r-10), border)
    cloth.paste(badge, (cx-r, cy-r), mask)
    if kind in ("pile", "wings", "eclipse"):
        laurel(d, cx, cy+5, r+19, gold)
    return cloth


def western_banner(source: Image.Image, flag_id: str, patron: str | None = None) -> Image.Image:
    if flag_id == "WRK_veyran_empire":
        return veyran_crown(source)
    if flag_id == "WRK_republican_union":
        return union_standard()
    if patron == "WRK":
        return western_subject_standard(source, WEST_MANDATE_FLAGS[flag_id][0])
    cloth = source.convert("RGB").resize(CANVAS, Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(cloth)
    if patron:
        # A broad hoist carries the patron's device. The national arms stay on the fly.
        field, metal = "#174a41", "#edc168"
        cloth.paste(cloth.resize((464, 416), Image.Resampling.LANCZOS), (192, 0))
        draw.rectangle((0, 0, 184, 415), fill=field)
        draw.rectangle((180, 0, 203, 415), fill=metal)
        draw.polygon(((38, 134), (146, 134), (146, 218), (92, 278), (38, 218)), fill=metal)
        draw.polygon(((60, 156), (124, 156), (124, 208), (92, 244), (60, 208)), fill=field)
    else:
        # The paired gold bands and star of victory leave the national arms on the hoist.
        field = cloth.resize((571, 320), Image.Resampling.LANCZOS)
        ink, metal = "#202936", "#efd18a"
        draw.rectangle((0, 0, 655, 415), fill=metal)
        cloth.paste(field, (0, 48))
        draw.polygon(((490, 0), (656, 0), (656, 416), (490, 416), (571, 208)), fill=ink)
        draw.line(((491, 0), (572, 208), (491, 416)), fill=metal, width=17)
        draw.polygon(points(614, 208, 34, 14, 4), fill=metal)
    return cloth


COPIED_FLAG_TRIPLETS = {
    "EYR": "VAD",
    "WRK_vorkerland_joint_government": "WRK",
    "IVN_unified_legion_west_victory": "IVN_unified_legion",
    "IVN_unified_legion_west_mandate": "IVN_unified_legion",
}


def add_triplet(
    outputs: dict[Path, Image.Image],
    flag_id: str,
    image: Image.Image,
) -> None:
    # Source artwork is an input. Procedural flags are reproducible from code;
    # neither route needs an additional generated source PNG.
    for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
        resized = image.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
        outputs[FLAG_ROOT / directory / f"{flag_id}.tga"] = resized


def add_runtime_triplet(
    outputs: dict[Path, Image.Image], flag_id: str, image: Image.Image
) -> None:
    prepared = image.convert("RGBA")
    if prepared.size != (82, 52):
        raise ValueError(f"{flag_id} runtime master must be 82x52, got {prepared.size}")
    for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
        supplied_size = SOURCE_ROOT / f"{flag_id}_{directory}.png"
        if directory and supplied_size.is_file():
            # Authored small masters retain details lost by resampling the main flag.
            with Image.open(supplied_size) as source:
                rendered = source.convert("RGBA")
            if rendered.size != size:
                raise ValueError(
                    f"{supplied_size.name} must be {size}, got {rendered.size}"
                )
        else:
            rendered = (
                prepared.copy()
                if prepared.size == size
                else prepared.resize(size, Image.Resampling.LANCZOS)
            )
        outputs[FLAG_ROOT / directory / f"{flag_id}.tga"] = rendered


def expected_outputs(tags: set[str] | None = None) -> dict[Path, Image.Image]:
    # A scoped build must not open unrelated optional source artwork.
    known = (
        set(BUILDERS)
        | set(SUPPLIED_FLAGS)
        | set(SUPPLIED_RUNTIME_FLAGS)
        | set(ARTWORK_FLAGS)
        | set(COPIED_FLAG_TRIPLETS)
        | set(WEST_VICTORY_FLAGS)
        | set(WEST_MANDATE_FLAGS)
    )
    if tags is not None and tags - known:
        raise ValueError(f"Unknown flag IDs: {sorted(tags - known)}")
    outputs: dict[Path, Image.Image] = {}
    for flag_id, builder in BUILDERS.items():
        if tags is not None and flag_id not in tags:
            continue
        add_triplet(outputs, flag_id, builder())

    for flag_id, supplied in (SUPPLIED_FLAGS | ARTWORK_FLAGS).items():
        if tags is not None and flag_id not in tags:
            continue
        with Image.open(supplied) as source:
            prepared = ImageOps.fit(
                source.convert("RGB"), CANVAS, method=Image.Resampling.LANCZOS
            )
        add_triplet(outputs, flag_id, prepared)

    for flag_id, supplied in SUPPLIED_RUNTIME_FLAGS.items():
        if tags is not None and flag_id not in tags:
            continue
        with Image.open(supplied) as source:
            add_runtime_triplet(outputs, flag_id, source)

    for target_flag_id, source_flag_id in COPIED_FLAG_TRIPLETS.items():
        if tags is not None and target_flag_id not in tags:
            continue
        for directory in (FLAG_ROOT, FLAG_ROOT / "medium", FLAG_ROOT / "small"):
            with Image.open(directory / f"{source_flag_id}.tga") as source:
                outputs[directory / f"{target_flag_id}.tga"] = source.convert("RGBA")

    def national_flag(source_id: str) -> Image.Image:
        path = FLAG_ROOT / f"{source_id}.tga"
        if path in outputs:
            return outputs[path]
        if source_id in known:
            # A scoped export still reads the canonical inputs of an owned national flag.
            return expected_outputs({source_id})[path]
        with Image.open(path) as source:
            return source.convert("RGB")

    for flag_id, source_id in WEST_VICTORY_FLAGS.items():
        if tags is None or flag_id in tags:
            add_triplet(outputs, flag_id, western_banner(national_flag(source_id), flag_id))
    for flag_id, (source_id, patron) in WEST_MANDATE_FLAGS.items():
        if tags is None or flag_id in tags:
            add_triplet(outputs, flag_id, western_banner(national_flag(source_id), flag_id, patron))
    return outputs


def validate_outputs(outputs: dict[Path, Image.Image]) -> list[str]:
    issues: list[str] = []
    for path, expected in outputs.items():
        if not path.is_file():
            issues.append(f"missing generated flag: {path.relative_to(ROOT)}")
            continue
        try:
            with Image.open(path) as source:
                actual = source.convert("RGBA")
        except OSError as exc:
            issues.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
            continue
        expected_rgba = expected.convert("RGBA")
        if actual.size != expected_rgba.size:
            issues.append(
                f"{path.relative_to(ROOT)} has size {actual.size}, expected {expected_rgba.size}"
            )
        elif any(
            channel.getbbox() is not None
            for channel in ImageChops.difference(actual, expected_rgba).split()
        ):
            issues.append(
                f"{path.relative_to(ROOT)} pixels differ from deterministic render"
            )
    return issues


def apply_outputs(outputs: dict[Path, Image.Image]) -> None:
    for path, image in outputs.items():
        if path.is_file() and not validate_outputs({path: image}):
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    # Cosmetic aliases intentionally reuse the canonical flag byte-for-byte.
    # Pillow normalizes the TGA header when saving an opened image, so restore
    # these triplets with a real file copy after rendering the authored flags.
    for target_flag_id, source_flag_id in COPIED_FLAG_TRIPLETS.items():
        for directory in (FLAG_ROOT, FLAG_ROOT / "medium", FLAG_ROOT / "small"):
            if directory / f"{target_flag_id}.tga" not in outputs:
                continue
            shutil.copyfile(
                directory / f"{source_flag_id}.tga",
                directory / f"{target_flag_id}.tga",
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Vorkerland successor-state flags."
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--check",
        action="store_true",
        help="compare current flags with deterministic renders (default)",
    )
    actions.add_argument(
        "--apply", action="store_true", help="write runtime TGA triplets"
    )
    parser.add_argument(
        "--tags", nargs="+", help="limit checks and writes to these flag IDs"
    )
    args = parser.parse_args()
    outputs = expected_outputs(set(args.tags) if args.tags else None)
    if args.apply:
        apply_outputs(outputs)
        print(
            f"Built {len({path.stem for path in outputs})} " "original flag triplets."
        )
    issues = validate_outputs(outputs)
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Vorkerland successor-state flag validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
