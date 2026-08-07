from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    start = match.start()
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {name}")


class WrkStartingIdeaTests(unittest.TestCase):
    SPIRITS = (
        "WRK_ashes_of_the_crown",
        "WRK_hourglass_of_discord",
        "WRK_constitution_of_the_republic",
        "WRK_birthplace_of_the_first_revolution",
    )

    def test_wrk_starts_with_all_four_spirits(self) -> None:
        history = read("history/countries/WRK - WorkerLand.txt")
        start_ideas = named_block(history, "add_ideas")
        for spirit in self.SPIRITS:
            self.assertIn(spirit, start_ideas)

    def test_each_starting_spirit_is_strictly_negative(self) -> None:
        ideas = read("common/ideas/vorkerland.txt")
        expected_penalties = {
            "WRK_ashes_of_the_crown": (
                "send_volunteer_factor = -0.50",
                "army_attack_factor = -0.15",
                "army_org_factor = -0.20",
                "ADISCORD_country_development_army_growth_factor = -0.10",
            ),
            "WRK_hourglass_of_discord": (
                "political_power_gain = -0.25",
                "stability_factor = -0.10",
                "ADISCORD_country_development_economic_growth_factor = -0.15",
            ),
            "WRK_constitution_of_the_republic": (
                "stability_factor = -0.10",
                "political_power_gain = -0.15",
                "consumer_goods_factor = 0.10",
            ),
            "WRK_birthplace_of_the_first_revolution": (
                "stability_factor = -0.05",
                "research_speed_factor = -0.05",
                "ADISCORD_country_development_cultural_growth_factor = -0.10",
            ),
        }
        for spirit, penalties in expected_penalties.items():
            with self.subTest(spirit=spirit):
                block = named_block(ideas, spirit)
                self.assertIn("removal_cost = -1", block)
                self.assertIn("modifier = {", block)
                for penalty in penalties:
                    self.assertIn(penalty, block)
        constitution = named_block(ideas, "WRK_constitution_of_the_republic")
        self.assertNotIn("stability_factor = 0.25", constitution)

    def test_revolutionary_spirit_cancels_outside_vorkerist_family(self) -> None:
        ideas = read("common/ideas/vorkerland.txt")
        spirit = named_block(ideas, "WRK_birthplace_of_the_first_revolution")
        cancel = named_block(spirit, "cancel")
        self.assertIn("NOT =", cancel)
        self.assertIn("OR =", cancel)
        self.assertIn("has_country_leader_ideology = vorkerism", cancel)
        self.assertIn("has_country_leader_ideology = neo_vorkerism", cancel)

    def test_revolutionary_spirit_has_wired_square_icon(self) -> None:
        gfx = read("interface/ADISCORD_ideas.gfx")
        self.assertRegex(
            gfx,
            r'(?s)name\s*=\s*"GFX_idea_WRK_birthplace_of_the_first_revolution".*?'
            r'texturefile\s*=\s*"gfx/interface/ideas/WRK/WRK_the_empire_in_flames.png"',
        )
        icon = ROOT / "gfx/interface/ideas/WRK/WRK_the_empire_in_flames.png"
        self.assertTrue(icon.is_file(), icon)
        with Image.open(icon) as image:
            self.assertEqual(image.size[0], image.size[1])
            self.assertGreaterEqual(image.size[0], 64)
            self.assertEqual(image.mode, "RGBA")

    def test_russian_localisation_explains_the_revolution_and_removal(self) -> None:
        path = ROOT / "localisation/russian/ADISCORD_ideas_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        localisation = path.read_text(encoding="utf-8-sig")
        self.assertIn(
            'WRK_birthplace_of_the_first_revolution: "Родина Первой революции"',
            localisation,
        )
        description = re.search(
            r'^\s*WRK_birthplace_of_the_first_revolution_desc:\s*"(.+)"$',
            localisation,
            re.MULTILINE,
        )
        self.assertIsNotNone(description)
        text = description.group(1).lower()
        for concept in (
            "монархия",
            "свержение престола",
            "контрреволюцией",
            "не связанной с воркеризмом",
        ):
            self.assertIn(concept, text)


if __name__ == "__main__":
    unittest.main()
