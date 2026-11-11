from __future__ import annotations

from itertools import product
from pathlib import Path
import hashlib
import json
import re
import unittest

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = ROOT / "common/intelligence_agencies/00_intelligence_agencies.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_intelligence_agencies.txt"
TAGS = ("STP", "VAL", "NAM", "SHL", "RUS", "WRK", "NOD", "IVN", "VAD", "WKR", "TVA", "STS", "SRP")
INITIALIZE = "ADISCORD_initialize_intelligence_agency"


def value(entries, key):
    return next(entry.value for entry in entries if entry.key == key)


def read(path):
    return parse_clausewitz(path.read_text(encoding="utf-8-sig"))


def matches(entries, facts):
    def match(entry):
        key, expected = entry.key, entry.value
        if key == "OR":
            return any(match(child) for child in expected)
        if key in ("AND", "hidden_trigger"):
            return matches(expected, facts)
        if key == "NOT":
            return not any(match(child) for child in expected)
        if key == "always":
            return expected == "yes"
        if key in ("tag", "original_tag"):
            if expected == "event_target:ADISCORD_vorkerland_nation":
                expected = facts.get("nation", "WRK")
            return facts["tag"] == expected
        if key in ("has_dlc", "has_cosmetic_tag", "has_completed_focus"):
            return expected in facts.get(key, set())
        if key in ("exists", "has_intelligence_agency"):
            return facts.get(key, False) == (expected == "yes")
        if key == "check_variable":
            if value(expected, "compare") != "equals":
                raise AssertionError("Unsupported comparison in agency catalogue")
            return facts.get(value(expected, "var"), 0) == float(value(expected, "value"))
        raise AssertionError(f"Unsupported agency predicate: {key}")

    return all(match(entry) for entry in entries)


class IntelligenceAgencyTests(unittest.TestCase):
    def profiles(self):
        profiles = [entry.value for entry in read(CATALOGUE) if entry.key == "intelligence_agency"]
        self.assertTrue(profiles, "Agency catalogue is empty")
        return profiles

    def test_one_default_for_every_country_and_political_course(self):
        profiles = self.profiles()
        for tag, course, charter, empire in product(TAGS + ("EFL",), range(6), (False, True), (None, "RUS_last_empire", "RUS_black_banner_empire")):
            facts = {
                "tag": tag,
                "SHL_political_course": course,
                "has_completed_focus": {"NAM_federal_charter"} if charter else set(),
                "has_cosmetic_tag": {empire} if empire else set(),
            }
            defaults = [p for p in profiles if matches(value(p, "default"), facts)]
            with self.subTest(facts=facts):
                self.assertEqual(len(defaults), 1)
                self.assertTrue(matches(value(defaults[0], "available"), facts))
                picture = value(defaults[0], "picture")
                if tag == "EFL":
                    self.assertEqual(picture, "GFX_ADISCORD_agency_generic")
                else:
                    self.assertTrue(picture.startswith(f"GFX_ADISCORD_agency_{tag.lower()}"))

    def test_creation_requires_dlc_existing_country_and_no_existing_agency(self):
        effect = value(read(EFFECTS), INITIALIZE)
        guard = value(value(effect, "if"), "limit")
        for tag, exists, dlc, agency in product(TAGS + ("EFL",), (False, True), (False, True), (False, True)):
            facts = {"tag": tag, "exists": exists, "has_dlc": {"La Resistance"} if dlc else set(), "has_intelligence_agency": agency}
            with self.subTest(facts=facts):
                self.assertEqual(matches(guard, facts), tag in TAGS and exists and dlc and not agency)
        body = value(effect, "if")
        self.assertEqual([e.key for e in body if e.key != "limit"], ["create_intelligence_agency"])
        self.assertEqual(value(body, "create_intelligence_agency"), "yes")

    def test_vorkerland_winner_keeps_its_own_profile(self):
        profiles = self.profiles()
        for winner in ("WKR", "VAD", "TVA"):
            facts = {"tag": winner, "nation": winner}
            defaults = [p for p in profiles if matches(value(p, "default"), facts)]
            self.assertEqual(len(defaults), 1)
            self.assertEqual(value(defaults[0], "picture"), f"GFX_ADISCORD_agency_{winner.lower()}")
            imperial = next(p for p in profiles if value(p, "picture") == "GFX_ADISCORD_agency_wrk")
            self.assertFalse(matches(value(imperial, "available"), facts))

    def test_emblems_do_not_leak_to_other_countries_or_courses(self):
        profiles = self.profiles()
        for profile in profiles:
            picture = value(profile, "picture")
            for tag in TAGS + ("EFL",):
                facts = {"tag": tag}
                available = matches(value(profile, "available"), facts)
                if picture != "GFX_ADISCORD_agency_generic" and available:
                    self.assertEqual(picture, f"GFX_ADISCORD_agency_{tag.lower()}")
        for course in range(1, 6):
            choices = [value(p, "picture") for p in profiles if matches(value(p, "available"), {"tag": "SHL", "SHL_political_course": course})]
            self.assertEqual(len([p for p in choices if p.startswith("GFX_ADISCORD_agency_shl_")]), 1)

    def test_successor_and_startup_calls_are_present(self):
        startup = (ROOT / "common/on_actions/00_ADISCORD_on_actions.txt").read_text(encoding="utf-8-sig")
        self.assertEqual(startup.count(f"{INITIALIZE} = yes"), 1)
        self.assertLess(startup.index("has_global_flag = ADISCORD_fresh_campaign_contract_v1"), startup.index(f"{INITIALIZE} = yes"))
        stp = read(ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertEqual(value(value(stp, "STP_cw_prepare_successor"), INITIALIZE), "yes")
        vorkerland = read(ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        partition = value(vorkerland, "ADISCORD_vorkerland_apply_initial_map")
        materialized = next(
            index for index, entry in enumerate(partition)
            if entry.key == "ADISCORD_vorkerland_relocate_legacy_armies"
        )
        for tag in ("WKR", "VAD", "TVA"):
            calls = [
                index for index, entry in enumerate(partition)
                if entry.key == tag
                and any(child.key == INITIALIZE for child in entry.value)
            ]
            self.assertEqual(len(calls), 1)
            self.assertGreater(calls[0], materialized)

    def test_graphics_and_localisation_contract(self):
        profiles = self.profiles()
        sprites = value(read(ROOT / "interface/ADISCORD_intelligence_agencies.gfx"), "spriteTypes")
        sprites = {value(s.value, "name"): s.value for s in sprites}
        pictures = [value(p, "picture") for p in profiles]
        self.assertEqual(len(pictures), len(set(pictures)))
        manifest_path = ROOT / "tools/assets/source/intelligence_agencies/agency_art_prompts.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        exports = {item["runtime_file"]: item for item in manifest["assets"]}
        self.assertEqual(len(exports), len(profiles))
        localisation = {
            language: "\n".join(
                path.read_text(encoding="utf-8-sig")
                for path in (ROOT / "localisation" / language).glob("ADISCORD*.yml")
            )
            for language in ("russian", "english")
        }
        for profile in profiles:
            sprite = sprites[value(profile, "picture")]
            self.assertEqual(value(sprite, "noOfFrames"), "2")
            texture = value(sprite, "texturefile")
            self.assertEqual(
                hashlib.sha256((ROOT / texture).read_bytes()).hexdigest(),
                exports[texture]["runtime_sha256"],
            )
            image = Image.open(ROOT / texture)
            self.assertEqual(image.size, (238, 119))
            self.assertEqual(image.mode, "RGBA")
            for offset in (0, 119):
                alpha = image.crop((offset, 0, offset + 119, 119)).getchannel("A")
                self.assertEqual(alpha.getextrema(), (0, 255))
                self.assertIsNotNone(alpha.getbbox())
            names = [entry.key or entry.value for entry in value(profile, "names")]
            for language in ("russian", "english"):
                for name in names:
                    self.assertRegex(localisation[language], rf'(?m)^\s*{re.escape(name)}:\s*(?:0\s*)?"[^\n]+"\s*$')
        for path in (CATALOGUE, EFFECTS):
            self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        loc = ROOT / "localisation/russian/ADISCORD_intelligence_agencies_l_russian.yml"
        self.assertTrue(loc.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
