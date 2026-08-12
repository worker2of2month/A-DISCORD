#!/usr/bin/env python3
"""Populate the compact Nodrul-controlled Ainholm mandate in states 118-120."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw
from tools.lib.localisation import replace_generated_localisation_block
from tools.lib.paths import repository_root


ROOT = repository_root()
STATE_DIR = ROOT / "history" / "states"
UNIT_PATH = ROOT / "history" / "units" / "AIN.txt"
COUNTRY_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "countries_l_russian.yml"
PARTY_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "parties_l_russian.yml"
CHARACTER_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "nsb_characters_l_russian.yml"
TRAIT_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "ADISCORD_traits_l_russian.yml"
IDEA_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "ADISCORD_ideas_l_russian.yml"
VP_LOCALISATION_PATH = ROOT / "localisation" / "russian" / "victory_points_l_russian.yml"
FLAG_DIR = ROOT / "gfx" / "flags"
DIVISION_TEMPLATE_NAMES = ("Licensed Security Battalion",)

AIN_LOCALISATION = {
    COUNTRY_LOCALISATION_PATH: {
        "AIN": "Айнхольмский мандат",
        "AIN_DEF": "Айнхольмский мандат",
        "AIN_ADJ": "Айнхольмск.",
    },
    PARTY_LOCALISATION_PATH: {
        "AIN_hedonism_party": "Лицензионная палата",
        "AIN_hedonism_party_long": "Палата нодрульских лицензий и местных концессионеров",
    },
    CHARACTER_LOCALISATION_PATH: {
        "AIN_Elias_Marven": "Элиас Марвен",
        "AIN_Elias_Marven_desc": "Нодрульский юрист и управляющий концессиями Марвен превратил временный договор об охране Айнхольма в бессрочный мандат. Выборы здесь проходят регулярно, но право попасть в бюллетень, открыть предприятие или покинуть долину выдаёт одна и та же лицензионная палата.",
    },
    TRAIT_LOCALISATION_PATH: {
        "AIN_concessionary_director": "Концессионный директор",
        "AIN_concessionary_director_desc": "Умеет превращать зависимость в аккуратный договор, а изъятие ресурсов — в платную государственную услугу.",
    },
    IDEA_LOCALISATION_PATH: {
        "AIN_concession_economy": "Концессионная экономика",
        "AIN_concession_economy_desc": "Промышленность, добыча и основные дороги Айнхольма переданы компаниям, связанным с Нодрульской республикой. В обмен колониальная администрация получает инвестиции и доступ к рынкам, однако значительная часть доходов и ресурсов уходит метрополии.",
    },
}

STATE_PROFILES = {
    118: {
        "owner": "AIN",
        "core": "AIN",
        "claims": ("TFF",),
        "provinces": (147,),
        "population": 420_000,
        "category": "town",
        "local_supplies": 3.0,
        "resources": {"aluminium": 3},
        "buildings": {
            "infrastructure": 4,
            "industrial_complex": 2,
            "arms_factory": 1,
        },
        "victory_points": ((147, 6),),
    },
    119: {
        "owner": "AIN",
        "core": "AIN",
        "claims": ("TFF",),
        "provinces": (59, 96, 16342, 16348, 16358),
        "population": 190_000,
        "category": "rural",
        "local_supplies": 2.2,
        "resources": {"steel": 3, "tungsten": 4},
        "buildings": {"infrastructure": 3, "arms_factory": 1},
        "victory_points": ((16348, 2),),
    },
    120: {
        "owner": "ORV",
        "core": "ORV",
        "claims": (),
        "provinces": (99, 109, 112, 123, 126, 142, 146, 151, 152, 16314),
        "population": 260_000,
        "category": "rural",
        "local_supplies": 2.0,
        "resources": {"chromium": 2, "steel": 5},
        "buildings": {"infrastructure": 2, "industrial_complex": 1},
        "victory_points": ((16314, 2),),
    },
}


def state_path(state_id: int) -> Path:
    matches = sorted(STATE_DIR.glob(f"{state_id}-*.txt"))
    if len(matches) != 1:
        raise RuntimeError(f"state {state_id}: expected one history file, found {len(matches)}")
    return matches[0]


def render_state(state_id: int, profile: dict[str, object]) -> str:
    resources = profile["resources"]
    buildings = profile["buildings"]
    victory_points = profile["victory_points"]
    lines = [
        "state = {",
        f"\tid = {state_id}",
        f'\tname = "STATE_{state_id}"',
        f"\tmanpower = {profile['population']}",
        f"\tstate_category = {profile['category']}",
        "\thistory = {",
        f"\t\towner = {profile['owner']}",
        f"\t\tadd_core_of = {profile['core']}",
    ]
    for claimant in profile["claims"]:
        lines.append(f"\t\tadd_claim_by = {claimant}")
    for province_id, value in victory_points:
        lines.append(f"\t\tvictory_points = {{ {province_id} {value} }}")
    lines.append("\t\tbuildings = {")
    for building, level in buildings.items():
        lines.append(f"\t\t\t{building} = {level}")
    lines.extend(("\t\t}", "\t}", "\tprovinces = {"))
    lines.append("\t\t" + " ".join(str(value) for value in profile["provinces"]))
    lines.append("\t}")
    if resources:
        lines.append("\tresources = {")
        for resource, value in sorted(resources.items()):
            lines.append(f"\t\t{resource} = {value}")
        lines.append("\t}")
    lines.extend(
        (
            "\tbuildings_max_level_factor = 1.000",
            f"\tlocal_supplies = {profile['local_supplies']:.1f}",
            "}",
            "",
        )
    )
    return "\n".join(lines)


def render_oob() -> str:
    template = DIVISION_TEMPLATE_NAMES[0]
    return """division_template = {
\tname = "%s"
\tregiments = {
\t\tinfantry = { x = 0 y = 0 }
\t\tinfantry = { x = 0 y = 1 }
\t\tinfantry = { x = 0 y = 2 }
\t\tinfantry = { x = 0 y = 3 }
\t}
}
units = {
\tdivision = { division_name = { is_name_ordered = yes name_order = 1 } location = 147 division_template = "%s" start_experience_factor = 0.10 start_equipment_factor = 0.72 }
\tdivision = { division_name = { is_name_ordered = yes name_order = 2 } location = 16348 division_template = "%s" start_experience_factor = 0.10 start_equipment_factor = 0.68 }
}
""" % (template, template, template)


def render_flag() -> Image.Image:
    width, height = 82, 52
    violet = (76, 52, 103)
    gold = (222, 184, 86)
    ivory = (229, 224, 211)
    image = Image.new("RGB", (width, height), violet)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=gold, width=3)
    draw.polygon(((0, 42), (53, 0), (68, 0), (15, 52), (0, 52)), fill=gold)
    draw.polygon(((9, 43), (56, 6), (63, 6), (16, 47)), fill=ivory)
    draw.ellipse((55, 17, 71, 33), outline=ivory, width=3)
    draw.rectangle((61, 29, 65, 43), fill=ivory)
    draw.rectangle((64, 38, 71, 42), fill=ivory)
    return image


def apply() -> None:
    for state_id, profile in STATE_PROFILES.items():
        state_path(state_id).write_text(render_state(state_id, profile), encoding="utf-8", newline="\n")
    UNIT_PATH.write_text(render_oob(), encoding="utf-8", newline="\n")
    for path, entries in AIN_LOCALISATION.items():
        replace_generated_localisation_block(
            path,
            "tools.builders.build_adiscord_ainholm_mandate",
            entries,
        )
    replace_generated_localisation_block(
        VP_LOCALISATION_PATH,
        "tools.builders.build_adiscord_ainholm_mandate",
        {
            "VICTORY_POINTS_147": "Айнхольм",
            "VICTORY_POINTS_16348": "Крейнский пост",
            "VICTORY_POINTS_16314": "Верхние ворота",
        },
    )
    # HOI4 expects 32-bit TGA flags; retaining alpha here avoids a runtime
    # loader warning even though the artwork itself is fully opaque.
    base = render_flag().convert("RGBA")
    for directory, size in (
        (FLAG_DIR, (82, 52)),
        (FLAG_DIR / "medium", (41, 26)),
        (FLAG_DIR / "small", (10, 7)),
    ):
        directory.mkdir(parents=True, exist_ok=True)
        image = base if base.size == size else base.resize(size, Image.Resampling.LANCZOS)
        image.save(directory / "AIN.tga")
    print("Applied Ainholm mandate: 3 states, 2 divisions, 3 flags and Russian localisation.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true", help="validate current generated outputs (default)")
    actions.add_argument("--apply", action="store_true", help="write states, OOB, flags and localisation")
    args = parser.parse_args()
    if args.apply:
        apply()
        return 0
    from tools.validators.validate_adiscord_ainholm_mandate import main as validate_main

    return validate_main()


if __name__ == "__main__":
    raise SystemExit(main())
