#!/usr/bin/env python3
"""Build original, small-format-readable flags for Vorkerland successor states."""

from __future__ import annotations

import math
from pathlib import Path
from shutil import copyfile

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
FLAG_ROOT = ROOT / "gfx" / "flags"
SOURCE_ROOT = FLAG_ROOT / "source"
CANVAS = (656, 416)


def points(cx: int, cy: int, outer: int, inner: int, count: int, offset: float = -math.pi / 2):
    result = []
    for index in range(count * 2):
        radius = outer if index % 2 == 0 else inner
        angle = offset + index * math.pi / count
        result.append((cx + round(math.cos(angle) * radius), cy + round(math.sin(angle) * radius)))
    return result


def ring(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str, width: int) -> None:
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
    draw.polygon(((328, 68), (470, 120), (446, 300), (328, 365), (210, 300), (186, 120)), fill=bone)
    draw.polygon(((328, 100), (430, 138), (412, 278), (328, 324), (244, 278), (226, 138)), fill="#314630")
    draw.line((267, 237, 389, 237), fill=gold, width=22)
    draw.line((287, 190, 369, 190), fill=gold, width=18)
    return image


def wtd() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#243f4b")
    draw = ImageDraw.Draw(image)
    pale, copper, deep = "#dde4d6", "#d18445", "#162b33"
    draw.rectangle((0, 0, 655, 415), outline=deep, width=24)
    draw.polygon(((328, 58), (455, 132), (455, 284), (328, 358), (201, 284), (201, 132)), fill=pale)
    draw.polygon(((328, 94), (420, 147), (420, 269), (328, 322), (236, 269), (236, 147)), fill=deep)
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
        draw.line((328, 248, 328 + math.cos(rad) * 225, 248 + math.sin(rad) * 225), fill=gold, width=15)
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
    draw.polygon(((170, 225), (278, 130), (332, 190), (395, 108), (486, 218), (396, 183), (332, 248), (270, 188)), fill=white)
    draw.ellipse((305, 176, 350, 221), fill=rose)
    return image


def tru() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#61302a")
    draw = ImageDraw.Draw(image)
    gold, dark = "#e4b552", "#30251f"
    draw.polygon(points(328, 180, 146, 105, 16), fill=gold)
    draw.ellipse((240, 92, 416, 268), fill=dark)
    draw.ellipse((266, 118, 390, 242), fill=gold)
    draw.polygon(((0, 416), (0, 345), (130, 260), (235, 335), (350, 245), (480, 345), (656, 275), (656, 416)), fill=dark)
    draw.line((0, 350, 656, 350), fill=gold, width=18)
    return image


def vla() -> Image.Image:
    image = Image.new("RGB", CANVAS, "#6c2e2e")
    draw = ImageDraw.Draw(image)
    stone, dark = "#e7dfce", "#332825"
    draw.polygon(((0, 0), (160, 0), (656, 300), (656, 416), (520, 416), (0, 105)), fill=dark)
    draw.rectangle((272, 110, 384, 350), fill=stone)
    draw.polygon(((246, 126), (410, 126), (380, 76), (350, 112), (328, 65), (303, 112), (275, 76)), fill=stone)
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
    draw.polygon(((0, 315), (155, 250), (315, 330), (480, 245), (656, 310), (656, 416), (0, 416)), fill=mint)
    draw.polygon(((355, 58), (443, 179), (405, 285), (328, 315), (256, 260), (265, 170)), fill=mint)
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


BUILDERS = {
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
    "ROM": SOURCE_ROOT / "ROM.png",
    "TRU": SOURCE_ROOT / "TRU.png",
    "IBA": SOURCE_ROOT / "IBA.png",
    "TRU_zolotorevsk_republic": SOURCE_ROOT / "TRU_zolotorevsk_republic.png",
    "WRK_vorkerland_utilitarian_republic": SOURCE_ROOT / "WRK_vorkerland_utilitarian_republic.png",
}

COPIED_FLAG_TRIPLETS = {
    "WRK_vorkerland_joint_government": "WRK",
}


def write_triplet(flag_id: str, image: Image.Image) -> None:
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    image.save(SOURCE_ROOT / f"{flag_id}.png")
    for directory, size in (("", (82, 52)), ("medium", (41, 26)), ("small", (10, 7))):
        target_dir = FLAG_ROOT / directory
        target_dir.mkdir(parents=True, exist_ok=True)
        resized = image.resize(size, Image.Resampling.LANCZOS).convert("RGBA")
        resized.save(target_dir / f"{flag_id}.tga")


def copy_triplet(source_flag_id: str, target_flag_id: str) -> None:
    for directory in (FLAG_ROOT, FLAG_ROOT / "medium", FLAG_ROOT / "small"):
        copyfile(directory / f"{source_flag_id}.tga", directory / f"{target_flag_id}.tga")


def main() -> None:
    for flag_id, builder in BUILDERS.items():
        write_triplet(flag_id, builder())

    for flag_id, supplied in SUPPLIED_FLAGS.items():
        with Image.open(supplied) as source:
            prepared = ImageOps.fit(source.convert("RGB"), CANVAS, method=Image.Resampling.LANCZOS)
        write_triplet(flag_id, prepared)

    for target_flag_id, source_flag_id in COPIED_FLAG_TRIPLETS.items():
        copy_triplet(source_flag_id, target_flag_id)

    total = len(BUILDERS) + len(SUPPLIED_FLAGS) + len(COPIED_FLAG_TRIPLETS)
    print(f"Built {total} original flag triplets.")


if __name__ == "__main__":
    main()
