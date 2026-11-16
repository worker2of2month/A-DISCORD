"""Pack land battalion silhouettes and their two-frame NATO counters."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageOps

from tools.builders.build_adiscord_support_company_icons import LARGE, MAP, TEXT, centered, draw_support_cross, strip
from tools.lib.adiscord_ui_surfaces import dds_bytes


ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "tools/assets/source/battalions/unit_silhouettes.png"
SUPPORT_ATLAS = ATLAS.with_name("support_and_vehicles.png")
HQ_ATLAS = ATLAS.with_name("regimental_and_hq.png")


@dataclass(frozen=True)
class Battalion:
    unit: str
    cell: int
    colour: str
    symbol: str
    size: tuple[int, int]
    native: tuple[str, str] | None = None

    support: bool = False
    textures: tuple[str, str, str, str] | None = None

    def paths(self):
        if self.textures:
            large, white, small, nato = self.textures
            return (LARGE / f"{large}.dds", MAP / f"{white}.dds",
                    TEXT / f"{small}.dds", TEXT / f"{nato}.dds")
        if self.native:
            counter, inline = self.native
            return (
                LARGE / f"unit_{counter}_icon.dds",
                MAP / f"onmap_unit_{counter}_icon.dds",
                TEXT / f"unit_{inline}_icon_small.dds",
                TEXT / f"nato_unit_{inline}_icon_small.dds",
            )
        name = "battalions/STP_taran" if self.unit == "STP_taran" else self.unit
        return (
            LARGE / f"{name}_icon.dds", MAP / f"{name}_icon.dds",
            TEXT / f"{name}_icon_small.dds", TEXT / f"nato_{self.unit}_icon_small.dds",
        )


# The six-column atlases start at cells 0, 18 and 30. Native stems are
# shared with the HQ security battalions through the game's sprite registry.
BATTALIONS = (
    Battalion("infantry", 0, "#91cfd1", "rifles", (46, 29), ("infantry", "infantry")),
    Battalion("ADISCORD_militia", 1, "#87c1be", "militia", (36, 27)),
    Battalion("ADISCORD_territorial", 2, "#6baeac", "territorial", (43, 28)),
    Battalion("ADISCORD_assault_infantry", 3, "#97d3d9", "assault", (51, 30)),
    Battalion("ADISCORD_marine_infantry", 4, "#6484bb", "marine", (45, 28)),
    Battalion("mountaineers", 5, "#85ae42", "mountain", (43, 28), ("mountain", "mountaineers")),
    Battalion("ADISCORD_urban_breacher", 6, "#90babc", "shield", (43, 30)),
    Battalion("ADISCORD_hazard_infantry", 7, "#a0ab58", "hazard", (42, 29)),
    Battalion("ADISCORD_combat_robots", 8, "#9babb7", "robot", (37, 31)),
    Battalion("hq_paratrooper", 9, "#b486ad", "airborne", (36, 30), ("paratroop", "paratrooper")),
    Battalion("ADISCORD_mechanized_infantry", 10, "#62b4ac", "mechanized", (49, 25)),
    Battalion("ADISCORD_light_tank", 11, "#bab447", "light", (35, 21), ("light_tank", "light_armor")),
    Battalion("ADISCORD_combat_platform", 12, "#bab447", "medium", (44, 24), ("medium_tank", "medium_armor")),
    Battalion("ADISCORD_heavy_platform", 13, "#bab447", "heavy", (51, 27), ("heavy_armor", "heavy_armor")),
    Battalion("ADISCORD_line_artillery", 14, "#ba4441", "field", (49, 24)),
    Battalion("ADISCORD_line_anti_tank", 15, "#ba4441", "anti_tank", (48, 21)),
    Battalion("ADISCORD_line_anti_air", 16, "#ba4441", "anti_air", (39, 29)),
    Battalion("railway_gun", 17, "#ba4441", "rail", (60, 25), ("railway_gun", "railway_gun")),
    Battalion("STP_taran", 18, "#bab447", "taran", (55, 29)),
    Battalion("ADISCORD_zeppelin", 19, "#8fa6d0", "airship", (58, 28),
              textures=("ADISCORD_zeppelin_icon", "ADISCORD_zeppelin_icon", "ADISCORD_zeppelin_icon",
                        "nato_ADISCORD_zeppelin_icon_small")),
    Battalion("motorized", 22, "#86aa46", "motorized", (49, 27), ("motorized", "motorized")),
    Battalion("artillery", 14, "#ba4441", "field", (47, 25), support=True,
              textures=("support_unit_art_icon", "onmap_unit_art_icon", "support_art_small", "nato_unit_artillery_icon_small")),
    Battalion("anti_tank", 15, "#ba4441", "anti_tank", (48, 22), support=True,
              textures=("support_unit_at_icon", "onmap_unit_at_icon", "support_AT_small", "nato_unit_anti_tank_icon_small")),
    Battalion("anti_air", 16, "#ba4441", "anti_air", (39, 29), support=True,
              textures=("support_unit_anti_air_icon", "onmap_unit_anti_air_icon", "support_AA_small", "nato_unit_anti_air_icon_small")),
    Battalion("field_hospital", 20, "#ac5254", "medical", (41, 28), support=True,
              textures=("support_unit_field_hospital_icon", "onmap_support_field_hospital_icon",
                        "support_field_hospital_small", "nato_unit_field_hospital_icon_small")),
    Battalion("logistics_company", 21, "#b99c51", "supply", (43, 27), support=True,
              textures=("support_unit_logistics_company_icon", "onmap_support_logistics_icon",
                        "support_logistics_small", "nato_unit_logistics_company_icon_small")),
    Battalion("ADISCORD_recon_platform", 29, "#b8b044", "armored_recon", (48, 29), support=True,
              textures=("support_unit_armored_recon_icon", "onmap_support_armored_recon_icon",
                        "support_armored_recon", "nato_ADISCORD_recon_platform_icon_small")),
    Battalion("recon", 23, "#b8b044", "scout", (36, 27), support=True, native=("recon", "recon")),
    Battalion("engineer", 26, "#bc5549", "engineer", (42, 23), support=True,
              textures=("unit_engineer_icon", "onmap_unit_engineer_icon", "support_engineer_small", "nato_unit_engineer_icon_small")),
    Battalion("signal_company", 24, "#c78046", "signal", (38, 30), support=True,
              textures=("support_unit_signal_company_icon", "onmap_support_signal_icon", "support_signal_small", "nato_unit_signal_company_icon_small")),
    Battalion("maintenance_company", 25, "#a26589", "repair", (35, 27), support=True,
              textures=("support_unit_maintenance_company_icon", "onmap_support_maintenance_icon", "support_maintenance_small", "nato_unit_maintenance_company_icon_small")),
    Battalion("military_police", 27, "#b7a945", "police", (32, 24), support=True,
              textures=("support_unit_military_police_icon", "onmap_support_military_police_icon", "support_military_police_small", "nato_unit_military_police_icon_small")),
    Battalion("ADISCORD_recovery_platform", 28, "#a26589", "recovery", (48, 29), support=True),
    Battalion("ADISCORD_regimental_fire_support", 30, "#ba4441", "mortar", (41, 28), support=True,
              textures=("support_unit_fire_support_icon", "onmap_unit_fire_support_icon",
                        "support_unit_fire_support_icon_small", "nato_ADISCORD_regimental_fire_support_icon_small")),
    Battalion("hq_support_company", 31, "#a2a7a8", "command", (43, 31), support=True,
              textures=("support_unit_hq_icon", "onmap_support_hq_icon",
                        "support_unit_hq_icon_small", "nato_unit_hq_support_company_icon_small")),
    Battalion("hq_naval_liaison", 32, "#c77940", "naval_liaison", (32, 29), support=True,
              textures=("support_unit_hq_naval_liason_icon", "onmap_support_hq_naval_liaison_icon",
                        "support_unit_hq_naval_liason_icon_small", "nato_unit_hq_naval_liaison_icon_small")),
    Battalion("hq_air_liaison", 33, "#c77940", "air_liaison", (39, 30), support=True,
              textures=("support_unit_hq_air_liason_icon", "onmap_support_hq_air_liaison_icon",
                        "support_unit_hq_air_liason_icon_small", "nato_unit_hq_air_liaison_icon_small")),
    Battalion("hq_specops", 34, "#c77940", "special_ops", (37, 31), support=True,
              textures=("support_unit_hq_specops_icon ", "onmap_support_hq_specops_icon",
                        "support_unit_hq_specops_icon_small", "nato_unit_hq_specops_icon_small")),
    Battalion("pioneer_support", 35, "#bc5549", "bridge", (48, 22), support=True,
              textures=("pioneers_support", "onmap_support_pioneers_icon",
                        "support_pioneer_small", "nato_unit_pioneer_support_icon_small")),
    Battalion("fake_intel_unit", 36, "#5789aa", "decoy", (32, 30),
              textures=("unit_fake_intel_unit_icon", "onmap_unit_fake_intel_unit_icon",
                        "fake_intel_unit_small", "nato_unit_fake_intel_unit_icon_small")),
    *(
        Battalion(f"{weight}_flame_tank", cell, "#bab447", f"flame_{weight}", size,
                  (f"{weight}_flamethrower_tank", f"{weight}_flame_tank"), support=True)
        for weight, cell, size in (
            ("light", 39, (41, 26)), ("medium", 40, (51, 25)), ("heavy", 41, (57, 27))
        )
    ),
)


GROUP_HEADERS = {
    "unit_mot_art_icon": Battalion("mobile_combat_support", 37, "#ba4441", "mobile_field", (62, 26)),
    "unit_medium_tank_artillery_icon": Battalion("armor_combat_support", 38, "#ba4441", "armored_field", (53, 28)),
}


def battalion_badge(symbol, field, ink):
    image = Image.new("RGBA", (42, 26), field)
    pen = ImageDraw.Draw(image)
    pen.rectangle((0, 0, 41, 25), outline=ink, width=2)
    infantry = {"rifles", "militia", "territorial", "assault", "marine", "mountain", "airborne", "mechanized"}
    if symbol in infantry:
        pen.line((2, 2, 39, 23), fill=ink, width=2)
        pen.line((2, 23, 39, 2), fill=ink, width=2)
    if symbol == "militia":
        for x in (15, 21, 27):
            pen.ellipse((x - 1, 4, x + 1, 6), fill=ink)
    elif symbol == "territorial":
        pen.line((3, 19, 38, 19), fill=ink, width=3)
    elif symbol == "assault":
        pen.line([(13, 11), (21, 4), (29, 11)], fill=ink, width=3)
    elif symbol == "marine":
        pen.line((21, 5, 21, 20), fill=ink, width=3)
        pen.arc((12, 6, 30, 21), 12, 168, fill=ink, width=3)
    elif symbol == "mountain":
        pen.polygon([(10, 24), (21, 12), (32, 24)], fill=ink)
    elif symbol == "airborne":
        pen.arc((10, 4, 32, 18), 180, 360, fill=ink, width=3)
    elif symbol in {"light", "medium", "heavy", "mechanized", "taran"}:
        pen.rounded_rectangle((6, 7, 35, 18), radius=6, outline=ink, width=3)
        if symbol == "light":
            pen.line((17, 15, 25, 9), fill=ink, width=2)
        if symbol in {"heavy", "taran"}:
            pen.line((11, 21, 30, 21), fill=ink, width=2)
        if symbol == "taran":
            pen.polygon([(18, 16), (21, 9), (24, 16)], fill=ink)
    elif symbol == "shield":
        pen.polygon([(12, 5), (29, 5), (28, 15), (21, 21), (13, 15)], fill=ink)
    elif symbol == "hazard":
        for x, y in ((18, 4), (11, 13), (24, 13)):
            pen.ellipse((x, y, x + 6, y + 6), outline=ink, width=2)
    elif symbol == "robot":
        pen.rectangle((13, 6, 28, 19), outline=ink, width=3)
        pen.line((17, 12, 24, 12), fill=ink, width=2)
    elif symbol in {"field", "rail"}:
        pen.ellipse((16, 8, 25, 17), fill=ink)
        if symbol == "rail":
            pen.line((5, 21, 36, 21), fill=ink, width=2)
    elif symbol == "anti_tank":
        pen.line([(4, 21), (21, 5), (37, 21)], fill=ink, width=3)
    elif symbol == "anti_air":
        pen.arc((5, 5, 37, 31), 180, 360, fill=ink, width=3)
    elif symbol == "airship":
        pen.arc((5, 5, 36, 27), 180, 360, fill=ink, width=3)
        pen.line((14, 18, 28, 18), fill=ink, width=3)
    elif symbol == "motorized":
        for x in (12, 28):
            pen.ellipse((x-3, 16, x+3, 22), fill=ink)
    elif symbol == "medical":
        pen.rectangle((18, 5, 23, 20), fill=ink)
        pen.rectangle((13, 10, 28, 15), fill=ink)
    elif symbol == "supply":
        pen.line((3, 13, 38, 13), fill=ink, width=3)
    elif symbol in {"scout", "armored_recon"}:
        pen.line((2, 23, 39, 2), fill=ink, width=3)
        if symbol == "armored_recon":
            pen.rounded_rectangle((7, 8, 34, 17), radius=5, outline=ink, width=2)
    elif symbol == "engineer":
        pen.line((10, 8, 31, 8), fill=ink, width=3)
        for x in (10, 20, 30):
            pen.line((x, 8, x, 18), fill=ink, width=3)
    elif symbol == "signal":
        pen.line([(5, 20), (21, 7), (18, 17), (36, 4)], fill=ink, width=3)
    elif symbol in {"repair", "recovery"}:
        pen.line((5, 13, 36, 13), fill=ink, width=3)
        pen.ellipse((16, 8, 26, 18), outline=ink, width=3)
        if symbol == "recovery":
            pen.line((10, 21, 31, 21), fill=ink, width=2)
    elif symbol == "police":
        pen.line([(7, 19), (7, 6), (13, 13), (19, 6), (19, 19)], fill=ink, width=2)
        pen.line([(25, 19), (25, 6), (33, 6), (35, 9), (33, 13), (25, 13)], fill=ink, width=2)
    elif symbol == "mortar":
        pen.ellipse((17, 13, 25, 21), fill=ink)
        pen.line((21, 5, 21, 16), fill=ink, width=3)
    elif symbol == "command":
        pen.line((3, 5, 3, 23), fill=ink, width=3)
        pen.polygon([(8, 5), (32, 5), (25, 11), (32, 15), (8, 15)], fill=ink)
        pen.line((8, 5, 8, 21), fill=ink, width=2)
    elif symbol == "naval_liaison":
        pen.line((21, 5, 21, 21), fill=ink, width=3)
        pen.line((15, 9, 27, 9), fill=ink, width=2)
        pen.arc((8, 7, 34, 21), 0, 180, fill=ink, width=3)
    elif symbol == "air_liaison":
        pen.line((21, 5, 21, 20), fill=ink, width=3)
        pen.polygon([(6, 15), (21, 8), (36, 15), (22, 13)], fill=ink)
        pen.line((16, 20, 26, 20), fill=ink, width=2)
    elif symbol == "special_ops":
        pen.polygon([(29, 3), (25, 15), (19, 17), (17, 14)], fill=ink)
        pen.line((12, 12, 23, 20), fill=ink, width=2)
        pen.line((18, 16, 11, 22), fill=ink, width=3)
    elif symbol == "bridge":
        pen.line([(5, 17), (11, 10), (30, 10), (37, 17)], fill=ink, width=3)
        for x in (12, 29):
            pen.line((x, 11, x, 20), fill=ink, width=3)
    elif symbol == "decoy":
        for start in (6, 16, 26):
            pen.line((start, 19 - (start - 6)//2, start+5, 16 - (start - 6)//2), fill=ink, width=3)
            pen.line((start, 6 + (start - 6)//2, start+5, 9 + (start - 6)//2), fill=ink, width=3)
    elif symbol.startswith("flame_"):
        pen.rounded_rectangle((7, 6, 35, 18), radius=6, outline=ink, width=2)
        pen.polygon([(16, 14), (21, 6), (21, 11), (26, 7), (24, 15)], fill=ink)
        for x in {"flame_light": (21,), "flame_medium": (16, 26), "flame_heavy": (13, 21, 29)}[symbol]:
            pen.rectangle((x-1, 20, x+1, 22), fill=ink)
    elif symbol in {"mobile_field", "armored_field"}:
        pen.ellipse((17, 6, 25, 14), fill=ink)
        if symbol == "armored_field":
            pen.rounded_rectangle((6, 4, 36, 20), radius=8, outline=ink, width=2)
        else:
            for x in (12, 29):
                pen.ellipse((x-2, 17, x+2, 21), fill=ink)
    return image


def silhouette(atlas, battalion, cell):
    w, h = 228, 126
    row, col = divmod(cell, 6)
    art = atlas.crop((w * col, h * row, w * (col + 1), h * (row + 1)))
    alpha = art.getchannel("A")
    bounds = alpha.point(lambda a: 255 if a >= 64 else 0).getbbox()
    if not bounds:
        raise ValueError(f"Empty silhouette: {battalion.unit}")
    relief = ImageOps.autocontrast(ImageOps.grayscale(art), cutoff=(2, 2), mask=alpha)
    rgb = ImageColor.getrgb(battalion.colour)
    shadow = tuple(round(v * 0.18) for v in rgb)
    light = tuple(round(v + (255 - v) * 0.42) for v in rgb)
    result = ImageOps.colorize(relief, shadow, light, mid=rgb, midpoint=150).convert("RGBA")
    if battalion.symbol.startswith("flame_"):
        red, _, blue, _ = art.split()
        plume = ImageChops.subtract(red, blue).point(lambda value: min(255, max(0, (value - 35) * 8)))
        result.paste(art, (0, 0), plume)
    result.putalpha(alpha)
    return result.crop(bounds)


def outputs(units=None):
    generated = {}
    with Image.open(ATLAS) as atlas, Image.open(SUPPORT_ATLAS) as extras, Image.open(HQ_ATLAS) as hq:
        for battalion in BATTALIONS:
            if units is not None and battalion.unit not in units:
                continue
            if battalion.cell >= 30:
                art = silhouette(hq, battalion, battalion.cell - 30)
            elif battalion.cell >= 18:
                art = silhouette(extras, battalion, battalion.cell - 18)
            else:
                art = silhouette(atlas, battalion, battalion.cell)
            ink = "#141914" if ImageColor.getcolor(battalion.colour, "L") >= 125 else "white"
            badge = battalion_badge(battalion.symbol, battalion.colour, ink)
            mono = battalion_badge(battalion.symbol, "white", "#171717")
            medium = centered(art, (76, 42), battalion.size)
            if battalion.support:
                draw_support_cross(medium)
            small = centered(art, (30, 12), (26, 12))
            white = ImageOps.grayscale(small).point(lambda v: 140 + v * 115 // 255).convert("RGBA")
            white.putalpha(small.getchannel("A"))
            frames = (
                strip(medium, centered(badge, (76, 42), badge.size)),
                strip(white, centered(mono, (30, 12), (23, 12))),
                strip(small, centered(badge, (30, 12), (23, 12))),
                centered(badge, (25, 12), (23, 12)),
            )
            for path, image in zip(battalion.paths(), frames, strict=True):
                generated[ROOT / path] = dds_bytes(image)
            if battalion.unit == "STP_taran":
                for path in battalion.paths()[:3]:
                    generated[ROOT / path.parent.parent / path.name] = generated[ROOT / path]
            if battalion.unit == "ADISCORD_line_artillery":
                generated[ROOT / LARGE / "unit_art_icon.dds"] = generated[ROOT / battalion.paths()[0]]
        for filename, group in GROUP_HEADERS.items():
            if units is not None and group.unit not in units:
                continue
            art = silhouette(hq, group, group.cell - 30)
            badge = battalion_badge(group.symbol, group.colour, "white")
            frames = strip(centered(art, (76, 42), group.size), centered(badge, (76, 42), badge.size))
            generated[ROOT / LARGE / f"{filename}.dds"] = dds_bytes(frames)
    return generated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", nargs="+", choices=[b.unit for b in (*BATTALIONS, *GROUP_HEADERS.values())])
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changed = 0
    for path, data in outputs(args.units).items():
        if path.is_file() and path.read_bytes() == data:
            continue
        changed += 1
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"Battalion icon files {'updated' if args.apply else 'different'}: {changed}")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
